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
import mesh_generator
import copy
from datetime import datetime, timedelta

# 创建日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建处理器 - 控制台处理器 (StreamHandler) 和文件处理器 (FileHandler)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('app.log')

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# 将处理器添加到记录器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

test_summary_file_path = ""
test_details_file = ""
current_time = ""

# 设置环境变量
os.environ["GTEST_CATCH_EXCEPTIONS"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"

default_production_well_event_config = {
                                    "Constraints": [
                                    ],
                                    "Date": "2000-01-01",
                                    "InjectedFluid": "",
                                    "MOLEFRAC": [
                                    ],
                                    "Status": "open",
                                    "Type": "producer"
                                }
default_injection_well_event_config = {"Constraints": [
                                    ],
                                    "Date": "2000-01-01",
                                    "InjectedFluid": "solvent",
                                    "MOLEFRAC": [
                                    ],
                                    "Status": "open",
                                    "Type": "injector"}

default_perforation_config = {
                                    "BlockBottom": 1200.5,
                                    "BlockIdx": [
                                    ],
                                    "BlockTop": 1201,
                                    "Connection": 0,
                                    "FF": 1,
                                    "Length": 0.5,
                                    "Status": "open"
                                }

default_production_well_config = {   
                            "test_item": True,
                            "DIR": "K",
                            "Events": [
                            ],
                            "GEOFAC": 0.37,
                            "Name": "PRO",
                            "Perforations": [
                            ],
                            "RW": { "test_item" : True, "value_range":[0.1, 1.0] },
                            "SKIN": 0,
                            "Status": "open",
                            "WFRAC": 1
                        }

default_injection_well_config = {
                            "test_item": True,
                            "DIR": "K",
                            "Events": [
                            ],
                            "GEOFAC": 0.37,
                            "Name": "INJ",
                            "Perforations": [
                            ],
                            "RW": { "test_item" : True, "value_range":[0.1, 1.0] },
                            "SKIN": 0,
                            "Status": "open",
                            "WFRAC": 1
                        }



# 初始化测试环境
# url 为 ip + port
def init_environment(url, template_file_path):

    global test_details_file,test_summary_file_path,current_time
    template_file_name = template_file_path.split("/")[-1]

    # 确认server在线，运行状态正常
    response = requests.get(url + f"/is_alive/{template_file_name}")
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
    current_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # 在脚本的同级目录下生成一个和当前时间戳相同的文件夹
    if os.path.exists(current_time):
        logger.warning(f"this test result storage already exits, please check it")
        return False
    
    os.makedirs(current_time)
    logger.info(f"this test result storage create success, path {os.path.abspath(current_time)}")

    # 在测试汇总页面创建一个条目
    response = requests.get(f"{url}/append_test_summary?name={template_file_name}测试&time={current_time}&link=/test_detail/{current_time}")
    #logger.info(response.text)
    if response.status_code == 200:
        logger.info(f"test summary add success, new test summary name: {template_file_name}测试")
    else:
        logger.warning(f"test summary {template_file_name}测试 add failed, please check it")
        return False
    
    return True

def analyze_json_array(json_array, need_test_keys):
    if isinstance(json_array, list):
        for item in json_array:
            if isinstance(item, list):
                analyze_json_array(item, need_test_keys)
            elif isinstance(item, dict):
                analyze_json(item, need_test_keys)


# 随机生成在指定范围内的日期
def random_date(start, end):
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_generated_date = start + timedelta(days=random_days)
    random_date_string = random_generated_date.strftime("%Y-%m-%d")
    return random_date_string


def analyze_json(json_object, need_test_keys):
    for key, value in json_object.items():
        
        # sgt 气液相渗表-气体饱和度主导特殊处理
        if key == "SGT" and "test_item" in value:
            json_object[key]["Values"].append([0, 0, 1, 0])
            
            # 拍脑袋想的，行数理论上可以更多
            sgt_table_row_count = random.randint(2, 20)
            sg_temp = 0
            krg_temp = 0
            krog_temp = 1
            pcog_temp = 0

            # 相渗表拍脑袋给个最大行数20行
            # 极小概率取到下界，小了不能再小
            for i in range(2, random.randint(3, 20)):
                sg_temp = random.uniform(sg_temp, 1)
                krg_temp = random.uniform(krg_temp, 1)
                krog_temp = random.uniform(0, krog_temp)
                pcog_temp = random.uniform(pcog_temp, 1)
                json_object[key]["Values"].append([sg_temp, krg_temp, krog_temp, pcog_temp])
            continue
        

        # 井相关配置特殊处理
        if key == "Wells" and isinstance(value, list) and not value:
            # 用防止井位置重复
            well_position_set = set()

            # 随机增加井的数量，先给个拍脑袋的数量1-10口吧
            well_num = random.randint(1,5)
            for i in range(0, well_num):
                well_object = {}
                well_type = random.randint(1,2)
                if well_type == 1:
                    well_object = copy.deepcopy(default_injection_well_config)
                elif well_type == 2:
                    well_object = copy.deepcopy(default_production_well_config)
                well_object["Name"] = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                value.append(well_object)

            for well_item in value:
                if "test_item" in well_item:
                    # 随机变更井事件的数量
                    event_num = random.randint(1,10)
                    for i in range(0, event_num):
                        random_num = random.randint(1, 2)
                        if random_num == 1:
                            well_item["Events"].append(copy.deepcopy(default_injection_well_event_config))
                        elif random_num == 2:
                            well_item["Events"].append(copy.deepcopy(default_production_well_event_config))
            
                    for event in well_item["Events"]:
                        # 注入井的注入溶剂的摩尔含量和注入的流体相关
                        mol_size = 6
                        #mol_size = len(event["MOLEFRAC"])
                        molefrac = []
                        for i in range(0, mol_size):
                            molefrac.append(0)

                        # 目前先不变更井的类型
                        if event["InjectedFluid"] == "solvent" or event["InjectedFluid"] == "water":
                            random_num = random.randint(1, 1)

                            if random_num == 0:
                                event["InjectedFluid"] = "water"

                            elif random_num == 1:
                                event["InjectedFluid"] = "solvent"

                                #设置各组分的摩尔含量
                                molefrac.clear()
                                upper_limit = 1
                                total_val = 0

                                for i in range(0, mol_size-1):
                                    temp_value = random.uniform(0, upper_limit)
                                    total_val = total_val + temp_value
                                    upper_limit = upper_limit - temp_value
                                    molefrac.append(temp_value)
                                molefrac.append(1-total_val)
                        event["MOLEFRAC"] = molefrac

                        # 控制条件
                        event["Constraints"] = []
                        temp_obj = {}
                        temp_obj["Action"] = "continue"
                        if event["InjectedFluid"] != "solvent" and event["InjectedFluid"] != "water":
                        # 对于生产井来说
                            # 目前只支持单生产控制条件
                            random_num = random.randint(1, 3)
                            if random_num == 1:    
                                temp_obj["Limit"] = "MIN"
                                temp_obj["Parameter"] = "BHP"
                                temp_obj["Value"] = random.randint(5000, 15000)

                            elif random_num == 2:
                                temp_obj["Limit"] = "MAX"
                                temp_obj["Parameter"] = "STO"
                                temp_obj["Value"] = random.uniform(0, 10000)

                            elif random_num == 3:
                                temp_obj["Limit"] = "MAX"
                                temp_obj["Parameter"] = "STL"
                                temp_obj["Value"] = random.uniform(0, 10000)
                        else:
                        # 对于注入井来说
                            random_num = random.randint(1, 2)
                            if random_num == 1:
                                temp_obj["Limit"] = "MAX"
                                temp_obj["Parameter"] = "BHP"
                                # 井底压力拍脑袋给一个
                                temp_obj["Value"] = random.randint(15000, 50000)

                            elif random_num == 2:
                                temp_obj["Limit"] = "MAX"
                                temp_obj["Parameter"] = "STG"
                                # 井底压力拍脑袋给一个
                                temp_obj["Value"] = random.uniform(100.0, 2000.0)

                        event["Constraints"].append(temp_obj)

                        # 随机生成一个井事件的时间
                        event["Date"] = random_date(datetime.strptime("2000-01-01", "%Y-%m-%d"), datetime.strptime("2100-01-01", "%Y-%m-%d"))

                        # 变更井的状态, 井关闭状态事件就跳过了，没有实际的处理意义
                        random_num = random.randint(1, 1)
                        if random_num ==1:
                            event["Status"] = "open"
                        elif random_num ==2:
                            event["Status"] = "close"

                # 几何因子，井分数，表皮因子暂时未生效，略过
                # 针对射孔来说，由于现阶段网格规格和井的修改无法联动，涉孔的数量就只能是一个或两个
                # 现在射孔只有射孔位置一个参数生效
                # 井状态这个参数目前无意义
                perforations_num = random.randint(1, 2)
                well_item["Perforations"] = []
                obj = copy.deepcopy(default_perforation_config)

                x_position = random.randint(1, 20)
                y_position = random.randint(1, 20)
                while True:
                    if (x_position, y_position) in well_position_set:
                        x_position = random.randint(1, 20)
                        y_position = random.randint(1, 20)
                    else:
                        well_position_set.add((x_position ,y_position))
                        break

                if perforations_num == 1:
                    z_position = random.randint(1, 2)
                    obj["BlockIdx"] = [x_position, y_position, z_position]
                    well_item["Perforations"].append(obj)
                elif perforations_num == 2:
                    obj["BlockIdx"] = [x_position, y_position, 1]

                    obj_temp = copy.deepcopy(obj)
                    obj["BlockIdx"] = [x_position, y_position, 2]

                    well_item["Perforations"].append(obj)
                    well_item["Perforations"].append(obj_temp)


        if key == "Reservoir" and isinstance(value, dict) and "test_item" in value:

            value_range_nx = value["Grid"]["NX"]["value_range"]
            value_range_ny = value["Grid"]["NY"]["value_range"]
            value_range_nz = value["Grid"]["NZ"]["value_range"]

            value["Grid"]["NX"] = random.randint(value["Grid"]["NX"]["value_range"][0], value["Grid"]["NX"]["value_range"][1])
            value["Grid"]["NY"] = random.randint(value["Grid"]["NY"]["value_range"][0], value["Grid"]["NY"]["value_range"][1])
            value["Grid"]["NZ"] = random.randint(value["Grid"]["NZ"]["value_range"][0], value["Grid"]["NZ"]["value_range"][1])

            # 网格实际尺寸也是拍脑袋想的
            i_var = []
            for i in range(0, value["Grid"]["NX"]):
                i_var.append(random.uniform(1, 100))
            value["Grid"]["IVAR"] = i_var

            j_var = []
            for i in range(0, value["Grid"]["NY"]):
                j_var.append(random.uniform(1, 100))
            value["Grid"]["JVAR"] = j_var

            k_var = []
            for i in range(0, value["Grid"]["NZ"]):
                k_var.append(random.uniform(1, 100))
            value["Grid"]["KVAR"] = k_var

            # 岩石压缩系数和参考压力未处理


        if isinstance(value, dict) and "test_item" in value and "value_range" in value:
            value_range = value["value_range"]
            if len(value_range) != 2:
                logger.warning(f"template file format error, value range error, error key:{key}")
                return False
            
            min_value = value_range[0]
            max_value = value_range[1]

            if isinstance(min_value, int):
                random_num = random.randint(min_value, max_value)
            else:
                random_num = random.uniform(min_value, max_value)
            json_object[key] = random_num
            need_test_keys.append(key)

        elif isinstance(value, dict):
            analyze_json(value, need_test_keys)

        elif isinstance(value, list):
            analyze_json_array(value, need_test_keys)

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
        object_js = json.load(f)

    # 遍历json，找出需要测试的key,并将需要测试的key赋予实际的值
    need_test_keys = []
    if analyze_json(object_js, need_test_keys):
        logger.info(f"need test keys: {need_test_keys}")
    else:
        return False
    
    # 将变更后的json文件输出到当次测试的对应文件夹中
    with open(f"{current_case_storage_path}/property.json", 'w', encoding='utf-8') as f:
        json.dump(object_js, f, ensure_ascii=False, indent=4)
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
def run_solver(case_id, template_file_path, test_data_object):
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

        zip_file_path = str(case_id) + ".zip"

        # 上传测试结果
        logger.info(f"test case {case_id} executed success!")
        response = requests.get(url + f"/append_test_details?test_id={current_time}&case_name={case_id}&result=pass&time={execution_time}s&result_file={zip_file_path}")
        #logger.info(response.text)
        if response.status_code == 200:
            logger.info(f"write result to test details success")
        else:
            logger.warning(f"write result to test details fail")

        test_data_object["success_times"] = test_data_object["success_times"] + 1 
        test_data_object["all_test_duration"] = test_data_object["all_test_duration"] + execution_time
        test_data_object["success_duration"] = test_data_object["success_duration"] + execution_time

    except subprocess.CalledProcessError as e:

        end_time = time.time()
        execution_time = end_time - start_time

        zip_file_path = str(case_id) + ".zip"

        response = requests.get(url + f"/append_test_details?test_id={current_time}&case_name={case_id}&result=fail&time={execution_time}s&result_file={zip_file_path}")
        logger.warning(f"test case {case_id} executed fail!")
        if response.status_code == 200:
            logger.info(f"write result to test details success")
        else:
            logger.warning(f"write result to test details fail")

        test_data_object["fail_times"] = test_data_object["fail_times"] + 1 
        test_data_object["all_test_duration"] = test_data_object["all_test_duration"] + execution_time
        test_data_object["fail_duration"] = test_data_object["fail_duration"] + execution_time

    # 将单次test_case的测试结果落地
    response = requests.get(url + f"/store_test_details_data")
    if response.status_code == 200:
            logger.info(f"store test details data success")
    else:
        logger.warning(f"store test details data fail")

    # 删除无用文件
    for file_name in os.listdir(current_case_storage_path):
        file_path = os.path.join(current_case_storage_path, file_name)

        if os.path.isfile(file_path) and (file_name != "property.json" and file_name != "output.log" and file_name != "template.json" and not file_name.endswith(".vts")) :  # 只处理文件
             os.remove(file_path)

    # 将结果文件压缩
    compress_directory_to_zip(current_case_storage_path, f"{current_time}/" + zip_file_path)

    # # 拷贝模板文件到当前文件夹
    # template_file_name = template_file_path.split("/")[-1]
    # shutil.copy(template_file_path, f"{current_case_storage_path}/{template_file_name}")

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


def clean_up():
    with open(f"./files/test_details.json", 'w', encoding='utf-8') as f:
        object_js = {}
        json.dump(object_js, f, ensure_ascii=False, indent=4)

    with open(f"./files/test_summary.json", 'w', encoding='utf-8') as f:
        object_js = {}
        object_js["test_summary"] = {}
        json.dump(object_js, f, ensure_ascii=False, indent=4)

    # 确认server在线，运行状态正常
    response = requests.get(url + f"/re_load_data")
    #logger.info(response.text)
    if response.status_code == 200:
        logger.info(f"{response.text}")
    else:
        logger.warning(f"re-load data failed")
        return False
    return True

def run_auto_test(url, template_file_path, total_test_time):

    if init_environment(url, template_file_path):
        logger.info(f"environment initial success")
    else:
        logger.error(f"environment initial failed")
        return

    test_data_object = {}
    # 成功次数
    test_data_object["success_times"] = 0
    # 失败次数
    test_data_object["fail_times"] = 0
    # 测试总时长
    test_data_object["all_test_duration"] = 0
    # 成功总时长
    test_data_object["success_duration"] = 0
    # 失败总时长
    test_data_object["fail_duration"] = 0

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
        mesh_generator.mesh_generator_interface(f"{current_time}/{i}/property.json", f"mesh", logger)
        logger.info(f"mesh generate finish")
        run_solver(i, template_file_path, test_data_object)
        logger.info(f"test case {i} finish")

    # 将测试的汇总结果更新到表格
    success_rate = float(test_data_object["success_times"]/int(total_test_time))
    average_time = float(test_data_object["all_test_duration"]/int(total_test_time))
    average_success_time = float(test_data_object["success_duration"]/test_data_object["success_times"]) if test_data_object["success_times"] > 0 else -1
    average_fail_time = float(test_data_object["fail_duration"]/test_data_object["fail_times"]) if test_data_object["fail_times"] > 0 else -1
    template_file_name = template_file_path.split("/")[-1]
    response = requests.get(url + f"/update_test_summary?name={template_file_name}测试&success_rate={success_rate}&average_time={average_time}&average_success_time={average_success_time}&average_fail_time={average_fail_time}")
    if response.status_code == 200:
            logger.info(f"update test summary data success")
    else:
        logger.warning(f"update test summary data fail")

    
    # 将单轮测试结果落地 
    response = requests.get(url + f"/store_test_summary_data")
    if response.status_code == 200:
            logger.info(f"store test summary data success")
    else:
        logger.warning(f"store test summary data fail")


    # 发送飞书消息
    #send_message_to_feishu()


if __name__ == '__main__':
    argv = sys.argv
    url = argv[1]
    template_file_folder = os.path.abspath(argv[2])
    total_test_time = argv[3]

     # 执行环境清理，对于单次测试来说，只是简单的把落地文件的内容清空
    if not clean_up():
        logger.error(f"re-load data failed")
        exits(1)

    for file in os.listdir(template_file_folder):
        file_path = os.path.join(template_file_folder, file)
        if os.path.isfile(file_path):
            run_auto_test(url, file_path, total_test_time)

