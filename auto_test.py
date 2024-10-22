#!/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import requests
import logging
import random
import time
import zipfile
import subprocess
import shutil
from datetime import datetime

logging.basicConfig(level=logging.INFO, filename='./app.log', filemode='a', 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


test_summary_file_path = ""
test_details_file = ""
current_time = ""

# 设置环境变量
os.environ["GTEST_CATCH_EXCEPTIONS"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"

# 初始化测试环境
# url 为 ip + port
def init_environment(url):

    global test_details_file,test_summary_file_path,current_time

    # 确认server在线，运行状态正常
    response = requests.get(url + "/is_alive")
    #logger.info(response.text)
    if response.status_code == 200:
        json_obj = json.loads(response.text)
        test_summary_file_path = json_obj["test_summary_file_path"]
        test_details_file = json_obj["test_details_file"]
        logger.info(f"test summary file path: {test_summary_file_path}, test details file: {test_details_file}")
    else:
        logger.warning(f"something wrong with server, please check it")
        return False
    
    # 获取当前时间，格式为YYYY-MM-DD-HH-MM
    current_time = datetime.now().strftime("%Y-%m-%d-%H-%M")
    # 在脚本的同级目录下生成一个和当前时间戳相同的文件夹
    if os.path.exists(current_time):
        logger.warning(f"this test result storage already exits, please check it")
        return False
    
    os.makedirs(current_time)
    logger.info(f"this test result storage create success, path {os.path.abspath(current_time)}")

    # 在测试汇总页面创建一个条目
    response = requests.get(f"{url}/append_test_summary?name={current_time}测试&time={current_time}&link=/test_detail/{current_time}")
    #logger.info(response.text)
    if response.status_code == 200:
        logger.info(f"test summary add success, new test summary name: {current_time}测试")
    else:
        logger.warning(f"test summary {current_time}测试 add failed, please check it")
        return False
    
    return True


def analyze_json(json_object, need_test_keys):
    for key, value in json_object.items():
        if isinstance(value, dict) and "test_item" in value and "value_range" in value:
            value_range = value["value_range"]
            if len(value_range) != 2:
                logger.warning(f"template file format error, value range error, error key:{key}")
                return False
            
            min_value = value_range[0]
            max_value = value_range[1]

            random_num = random.randint(min_value, max_value)
            json_object[key] = random_num
            need_test_keys.append(key)

        elif isinstance(value, dict):
            analyze_json(value, need_test_keys)

    return True
    

# 随机变更配置文件参数
def random_change_parameters(template_file_path, case_id):

    global current_time

    current_case_storage_path = f"{current_time}/" + str(case_id)
    logger.info(f"current case storage path: {os.path.abspath(current_case_storage_path)}")

    if os.path.exists(current_case_storage_path):
        logger.warning(f"this test case storage already exits, path: {current_case_storage_path}, please check it")
        return False

    os.makedirs(current_case_storage_path)

    with open(template_file_path, 'r') as f:
        object = json.load(f)

    # 遍历json，找出需要测试的key,并将需要测试的key赋予实际的值
    need_test_keys = []
    if analyze_json(object, need_test_keys):
        logger.info(f"need test keys: {need_test_keys}")
    else:
        return False
    
    # 将变更后的json文件输出到当次测试的对应文件夹中
    with open(f"{current_case_storage_path}/property.json", 'w', encoding='utf-8') as f:
        json.dump(object, f, ensure_ascii=False, indent=4)
    logger.info(f"property.json output success, output path {current_case_storage_path}/property.json")

    return True


# 压缩文件夹成zip包
def compress_directory_to_zip(source_dir, output_file):
    # 创建一个 zip 文件
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 遍历文件夹中的所有文件和子文件夹
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                # 获取文件的完整路径
                file_path = os.path.join(root, file)
                # 将文件添加到 zip 包中，保持相对路径
                zipf.write(file_path, arcname=os.path.relpath(file_path, source_dir))


# 进行单次求解（即运行单次测试）
def run_solver(case_id):
    global current_time

    current_case_storage_path = f"{current_time}/" + str(case_id)
    current_case_storage_path = os.path.abspath(current_case_storage_path)
    command = ["mpirun", "-n", "64", "./oil_solver", f"{current_case_storage_path}/property.json", "1"]

    
    # 启动子进程，捕获输出并等待其完成
    start_time = time.time()
    result = 0
    logger.info(f"executed command {command}")
    try:
        with open(f"{current_case_storage_path}/output.log", 'w', encoding='utf-8') as outfile:
            subprocess.run(command, check=True, stdout=outfile, stderr=outfile, text=True)

        end_time = time.time()
        execution_time = end_time - start_time

        zip_file_path = f"{current_time}/" + str(case_id) + ".zip"

        # 上传测试结果
        logger.info(f"test case {case_id} executed success!")
        response = requests.get(url + f"/append_test_details?test_id={current_time}&case_name={case_id}&result=pass&time={execution_time}s&result_file={zip_file_path}")
        #logger.info(response.text)
        if response.status_code == 200:
            logger.info(f"write result to test details success")
        else:
            logger.warning(f"write result to test details fail")

    except subprocess.CalledProcessError as e:

        end_time = time.time()
        execution_time = end_time - start_time

        zip_file_path = f"{current_time}/" + str(case_id) + ".zip"

        response = requests.get(url + f"/append_test_details?test_id={current_time}&case_name={case_id}&result=fail&time={execution_time}s&result_file={zip_file_path}")
        logger.warning(f"test case {case_id} executed fail!")
        if response.status_code == 200:
            logger.info(f"write result to test details success")
        else:
            logger.warning(f"write result to test details fail")

    # 将结果文件压缩
    compress_directory_to_zip(current_case_storage_path, zip_file_path)

    # 将单次test_case的测试结果落地
    response = requests.get(url + f"/store_test_details_data")
    if response.status_code == 200:
            logger.info(f"store test details data success")
    else:
        logger.warning(f"store test details data fail")

    # 删除无用文件
    for filename in os.listdir(current_case_storage_path):
        file_path = os.path.join(current_case_storage_path, filename)
        if os.path.isfile(file_path) and (filename != "property.json" and filename != "output.log") :  # 只处理文件
             os.remove(file_path)

    # 拷贝模板文件到当前文件夹
    shutil.copy("./template.json", f"{current_case_storage_path}/template.json") 

def send_message_to_feishu():

    # 构造飞书消息体部分
    test_details_url = f"{url}/test_detail/{current_time}"
    
    result = f"<at user_id=\"all\">所有人</at>\n {current_time}测试测试完毕\n 测试结果详情链接：{test_details_url}\n 测试总览链接: {url}" 

    # 构造消息json
    json_data = {}
    json_data["msg_type"]= "text" 
    json_data["content"]= { "text": result }
    json_string = json.dumps(json_data, ensure_ascii=False)

    # 将消息通过webhook的方式转发到飞书
    response = requests.post(
    "https://open.feishu.cn/open-apis/bot/v2/hook/13530db3-8fb8-47be-9456-59aea6699c88",
    headers={'Content-Type': 'application/json'},
    data=json_string.encode('utf-8'))
    
    # 如果请求错误则打印错误信息
    if response.status_code != 200:
        logger.warning("error code:", response.status_code)
        logger.warning("error msg:", response.text)

    logger.info("send message to feishu successfully.")


def run_auto_test(url, template_file_path, total_test_time):
    if init_environment(url):
        logger.info(f"environment initial success")
    else:
        logger.error(f"environment initial failed")
        return

    for i in range(0, int(total_test_time)):
        logger.info(f"----------------------------------")
        logger.info(f"")
        logger.info(f"")
        logger.info(f"test case {i} start")
        if random_change_parameters(template_file_path, i):
            logger.info(f"random change parameter success")
        else:
            logger.error1(f"random change parameter failed")
            return
        run_solver(i)
        logger.info(f"test case {i} finish")
    
    # 将单轮测试结果落地 
    response = requests.get(url + f"/store_test_summary_data")
    if response.status_code == 200:
            logger.info(f"store test summary data success")
    else:
        logger.warning(f"store test summary data fail")

    # 发送飞书消息
    send_message_to_feishu()


if __name__ == '__main__':
    argv = sys.argv
    url = argv[1]
    template_file_path = os.path.abspath(argv[2])
    total_test_time = argv[3]
    run_auto_test(url, template_file_path, total_test_time)

