import base64
import copy
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from future.backports.datetime import timedelta
from js2py import eval_js


def get_current_time(format_str):
    now = datetime.now()
    formatted_now = now.strftime(format_str)
    return formatted_now


def str_to_datetime(time_str, format_str):
    return datetime.strptime(time_str, format_str)


def file_write(file_path, content, mode, encoding='gbk'):
    if 'b' in mode:
        with open(file_path, mode) as f:
            f.write(content)
    else:
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)


def file_read(file_path, mode):
    with open(file_path, mode) as f:
        content = f.read()
    return content


def renew_loginMessage(old, new: str):
    login_data[old] = new
    file_write("loginMessage.txt", json.dumps(login_data, ensure_ascii=False, indent=4), "w", 'gbk')


def read_loginMessage():
    global if_login_success
    if os.path.exists(r"./loginMessage.txt") is False:
        login_message = requests.get(gitee_url + "/loginMessage.json").json()
        file_write("loginMessage.txt", json.dumps(login_message, ensure_ascii=False, indent=4), "w", 'gbk')
    try:
        login_message = json.loads(file_read(file_path=r"./loginMessage.txt", mode="r"))
    except json.JSONDecodeError:
        os.remove("./loginMessage.txt")
        print("状态信息：配置文件格式错误，请重新运行！")
        return {}
    while login_message['studentID'] == "" or login_message['password'] == "" or if_login_success is False:
        print("状态信息：信息不完整或填写错误，请重新填写！")
        os.startfile("loginMessage.txt")
        had_write = 'n'
        while had_write != 'y':
            had_write = input("提示信息：是否填写完毕？(y/n)")
        login_message = json.loads(file_read(file_path=r"./loginMessage.txt", mode="r"))
        if_login_success = True
    print(f"配置信息：{login_message}")
    return login_message


def base64_api(uname, pwd, img, typeid):
    with open(img, 'rb') as f_code:
        base64_data = base64.b64encode(f_code.read())
        b64 = base64_data.decode()
    data = {"username": uname, "password": pwd, "typeid": typeid, "image": b64}
    result = json.loads(requests.post("http://api.ttshitu.com/predict", json=data).text)
    if result['success']:
        return result["data"]["result"]
    else:
        return result["message"]


def login(student_id, password):
    global Cookies
    jsessionid_response = requests.post(academic_affairs_url)
    jsessionid = jsessionid_response.cookies.get("JSESSIONID")
    cookies = {
        "JSESSIONID": jsessionid,
    }
    renew_loginMessage('Cookies', jsessionid)
    Cookies = jsessionid
    # 获取验证码图片
    verify_code_url = academic_affairs_url + '/yzm?' + str(int(time.time() * 1000 + 3))
    verify_code_response = requests.get(url=verify_code_url, cookies=cookies).content
    # 保存验证码图片
    file_write("verify_code_image.jpg", verify_code_response, "wb")
    # 调用函数识别
    img_path = r"verify_code_image.jpg"
    verify_code = base64_api(uname='Jialifuniya', pwd='zxcvbnm123', img=img_path, typeid=3)
    if len(verify_code) == 4:
        os.remove(img_path)
    else:
        verify_code = 'abcd'
    # 密码加密使用了aes.js文件
    aes_response = requests.get(gitee_url + '/aes.js')
    file_write("aes.js", aes_response.content, "wb", "utf-8")
    # 读取 JavaScript 代码
    js_file_path = r'aes.js'
    # 检查文件是否存在
    js_code = ""
    if os.path.exists(js_file_path):
        js_code = file_read(js_file_path, 'r')
    else:
        print("状态信息：密码加密失败，请重试！")
    # 替换 JavaScript 代码中的变量
    js_code = js_code.replace('var account = "";', f'var account = "{student_id}";')
    js_code = js_code.replace('var password = "";', f'var password = "{password}";')
    js_code = js_code.replace('var verifycode = "";', f'var verifycode = "{verify_code}";')

    # 使用 js2py 执行 JavaScript 代码
    password_key = eval_js(js_code)
    # print("加密后的密码为："+password_key)
    os.remove(js_file_path)
    # 构造登录请求的参数
    init_login_data = {
        'account': student_id,
        'pwd': password_key,
        'verifycode': verify_code
    }
    # 发送登录请求
    login_response = requests.post(url=academic_affairs_url + '/new/login', data=init_login_data, headers=login_headers,
                                   cookies=cookies)
    return login_response.json()


def cookies_login():
    global login_code
    login_headers['Referer'] = 'https://jwc.htu.edu.cn/new/desktop'
    response = requests.get(url=academic_affairs_url + '/new/notice/countNotice', params={'_': time.time()},
                            cookies={'JSESSIONID': Cookies}, headers=login_headers)
    try:
        json.loads(response.text)
        login_code = 0
        print(f"登录信息：{response.json()}")
    except json.JSONDecodeError:
        print("登录信息：Cookies已过期")
        renew_loginMessage(old="Cookies", new='')


def adding(url, data):
    login_headers['Referer'] = 'https://jwc.htu.edu.cn/new/desktop'
    response = requests.post(url + '/add', data=data, cookies={'JSESSIONID': Cookies}, headers=login_headers)
    return response.json()


def add_course(config):
    course_types = ['公共任选', '专业选修', '教师教育']
    course_urls = ['/new/student/xsxk/xklx/01', '/new/student/xsxk/xklx/06', '/new/student/xsxk/xklx/07']
    course_index = course_types.index(config['type'])
    url = academic_affairs_url + course_urls[course_index]
    post_requests = []
    post_request = {}
    for course in config['courses']:
        course_code = course['course_code']
        course_name = course['course_name']
        data = {
            'kcrwdm': course_code,
            'kcmc': course_name,
            'qz': '-1',
            'hlct': '0'
        }
        post_request['url'] = url
        post_request['data'] = data
        post_requests.append(copy.deepcopy(post_request))
    print(f"选课信息：{post_requests}")
    print(f"选课时间：{config['start_time']}")
    while True:
        current_time = get_current_time('%Y-%m-%d %H:%M:%S.%f')
        print(f"\t\t\t\t{current_time}")
        if (str_to_datetime(current_time, "%Y-%m-%d %H:%M:%S.%f") >= str_to_datetime(config['start_time'], "%Y-%m-%d "
                                                                                                           "%H:%M:%S")
                - timedelta(seconds=2)):
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(adding, req["url"], req["data"]) for req in post_requests]
                for future_index in range(len(futures)):
                    response = futures[future_index].result()
                    print(f"{post_requests[future_index]['data']['kcmc']}: {response}")
            time.sleep(0.5)
        else:
            print("状态信息：未到选课时间")


if __name__ == '__main__':
    gitee_url = "https://gitee.com/xhand_xbh/hnu/raw/master"
    academic_affairs_url = "https://jwc.htu.edu.cn"
    print("""+-------------+--------+--------+------+
|     参数名   |     类型    |   说明   | 是否必填 |
+-------------+--------+--------+------+
|  studentID  |    字符串   |   学号    |  是   |
|  password   |    字符串   |   密码    |  是   |
|   Cookies   |    字符串   |  登录信息  |  否   |
| login_time  |    字符串   |  登录时间  |  否   |
| your_tasks  | 列表（整型） |  任务列表  |  固定  |
|   config    |    字典    |  任务配置   |  固定  |
|   number    |    整型    |   序号     |  固定  |
|    type     |    字符串   |  选课类型  |  是   |
| target_term |    字符串   |  目标学期  |  是   |
| start_time  |    字符串   | 选课开始时间 |  是   |
|  end_time   |    字符串   | 选课结束时间 |  否   |
|   courses   | 列表（字典） | 目标课程信息 |  是   |
| course_code |    字符串   |  课程代码   |  是   |
| course_name |    字符串   |  课程名称   |  是   |
+-------------+--------+--------+------+
""")
    login_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.58',
    }
    if_login_success = True
    login_code = -1
    login_data = None
    while login_code != 0:
        login_data = read_loginMessage()
        if not login_data:
            sys.exit()
        Cookies = login_data['Cookies']
        renew_loginMessage(old='login_time', new=get_current_time("%Y-%m-%d %H:%M:%S"))
        if Cookies != "":
            cookies_login()
        else:
            res = login(login_data['studentID'], login_data['password'])
            login_code = res['code']
            print(f"登录信息：{res}")
            if_login_success = login_code == 0
    print('\n')
    tasks_num = login_data['your_tasks']
    tasks = login_data['config']
    add_course(tasks)
