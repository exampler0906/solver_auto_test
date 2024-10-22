#!/bin/python3
# -*- coding: utf-8 -*-

# server.py
from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import json
import sys

app = Flask(__name__)

# 测试数据存储
test_summary_data = []
test_details = {}
test_summary_data_file = ""
test_details_file = ""


# 路由：测试汇总页面
@app.route('/')
def index():
    return render_template('index.html', tests=test_summary_data)

# 路由：测试详情页面
@app.route('/test_detail/<test_id>')
def test_detail(test_id):
    cases = test_details.get(test_id, [])
    return render_template('test_detail.html', cases=cases)

# 路由：下载落地文件
@app.route('/download/<test_id>/<filename>')
def download_file(test_id, filename):
    # 文件存储目录
    directory = os.path.join(app.root_path)
    return send_from_directory(directory, test_id + "/" +filename, as_attachment=True)

@app.route('/append_test_summary', methods=['GET'])
def append_test_summary():

    name = request.args.get('name')
    time = request.args.get('time')
    link = request.args.get('link')

    json_obj = {}
    json_obj["name"] = name
    json_obj["time"] = time
    json_obj["link"] = link
    test_summary_data.append(json_obj)
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


@app.route("/is_alive", methods=['GET'])
def get_alive():
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
