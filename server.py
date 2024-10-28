#!/bin/python3
# -*- coding: utf-8 -*-

# server.py
from flask import Flask, render_template, request, send_from_directory, jsonify, render_template_string
import os
import json
import sys

app = Flask(__name__)

# 测试数据存储
test_summary_data = {}
test_details = {}
test_summary_data_file = ""
test_details_file = ""
g_template_file_name = ""

# 路由：测试汇总页面
@app.route('/')
def index():
    return render_template('index.html', tests=test_summary_data)

# 路由：测试详情页面
@app.route('/test_detail/<test_id>')
def test_detail(test_id):
    cases = test_details.get(test_id, [])
    return render_template('test_detail.html', cases=cases, test_id = test_id, template_file_name=g_template_file_name)

# 路由：下载落地文件
@app.route('/download/<test_id>/<file_name>')
def download_file(test_id, file_name):
    # 文件存储目录
    directory = os.path.join(app.root_path)
    return send_from_directory(directory, test_id + "/" +file_name, as_attachment=True)

# 展示求解日志，模板文件和配置文件
@app.route('/show_file/<test_id>/<case_id>/<file_name>')
def show_file(test_id, case_id, file_name):
    # 文件存储目录
    directory = os.path.join(app.root_path)
    file_path = os.path.join(directory, test_id, case_id, file_name)
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        # 将文件内容展示在网页上
        return render_template_string("""
        <html>
        <head><title>File Content</title></head>
        <body>
            <h1>File: {{ file_name }}</h1>
            <pre>{{ content }}</pre>
        </body>
        </html>
        """, file_name=file_name, content=content)
    except FileNotFoundError:
        return  jsonify({"message":f"File '{file_name}' not found"}), 404


@app.route('/update_test_summary', methods=['GET'])
def update_test_summary():

    name = request.args.get('name')
    success_rate = request.args.get('success_rate')
    average_time = request.args.get('average_time')
    average_success_time = request.args.get('average_success_time')
    average_fail_time = request.args.get('average_fail_time')

    json_obj = {}
    json_obj["time"] = test_summary_data[name]["time"]
    json_obj["link"] = test_summary_data[name]["link"]
    json_obj["success_rate"] = str(float(success_rate)*100) + "%" 
    json_obj["average_time"] = average_time
    json_obj["average_success_time"] = average_success_time
    json_obj["average_fail_time"] = average_fail_time

    test_summary_data[name] = json_obj
    return jsonify({"message": "test summary updated successfully!", "new item": json_obj})


@app.route('/append_test_summary', methods=['GET'])
def append_test_summary():

    name = request.args.get('name')
    time = request.args.get('time')
    link = request.args.get('link')

    json_obj = {}
    json_obj["time"] = time
    json_obj["link"] = link
    json_obj["success_rate"] = ""
    json_obj["average_time"] = ""
    json_obj["average_success_time"] = ""
    json_obj["average_fail_time"] = ""
    test_summary_data[name]=json_obj
    return jsonify({"message": "test summary added successfully!", "new item": json_obj})


@app.route('/append_test_details', methods=['GET'])
def append_test_details():

    test_id = request.args.get('test_id')
    case_name = request.args.get('case_name')
    result = request.args.get('result')
    time = request.args.get('time')
    result_file = request.args.get('result_file')

    if test_id not in test_details:
        test_details[test_id] = []

    json_obj = {}
    json_obj["case_name"] = case_name
    json_obj["result"] = result
    json_obj["time"] = time
    json_obj["result_file"] = result_file
    test_details[test_id].append(json_obj)
    return jsonify({"message": "test details added successfully!", "new item": json_obj})


@app.route("/is_alive/<template_file_name>", methods=['GET'])
def get_alive(template_file_name):
    g_template_file_name = template_file_name
    return jsonify({"test_summary_file_path":test_summary_data_file, "test_details_file": test_details_file})


@app.route("/store_test_summary_data", methods=['GET'])
def store_test_summary_data_interface():
    global test_summary_data_file
    store_test_summary_data(test_summary_data_file)
    return jsonify({"message":"store test summary data success"})


@app.route("/store_test_details_data", methods=['GET'])
def store_test_details_data_interface():
    global test_details_file
    store_test_details_data(test_details_file)
    return jsonify({"message":"store test details data success"})


@app.route("/re_load_data", methods=['GET'])
def re_load_data():
    global test_summary_data,test_details
    load_data(test_summary_data_file, test_details_file)
    return jsonify({"message":"re-load data success"})

# 从落地文件中进行test_summary_data和test_details的加载，目前测试用例的tps不高于0.06，从文件读取性能足够
def load_data(test_summary_data_file, test_details_file):
    global test_summary_data,test_details
    with open(test_summary_data_file, 'r') as f:
        object = json.load(f)
        test_summary_data = object["test_summary"]

    with open(test_details_file, 'r') as f:
        test_details = json.load(f)

def store_test_summary_data(test_summary_data_file):
    global test_summary_data
    with open(test_summary_data_file, 'w', encoding='utf-8') as f:
        object = {}
        object["test_summary"] = test_summary_data
        json.dump(object, f, ensure_ascii=False, indent=4)


def store_test_details_data(test_details_file):
    global test_details
    with open(test_details_file, 'w', encoding='utf-8') as f:
        json.dump(test_details, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    
    # 从文件中加载测试数据
    argv = sys.argv
    test_summary_data_file = os.path.abspath(argv[1])
    test_details_file = os.path.abspath(argv[2])
    load_data(test_summary_data_file, test_details_file)

    app.run(host='0.0.0.0', port=5000, debug=True)
