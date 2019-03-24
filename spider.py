import requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
import re
import json
import pymongo
import os
from hashlib import md5
from multiprocessing import Pool

# 定义请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36',
    'referer': 'https://www.toutiao.com/search/?keyword=%E9%A3%8E%E6%99%AF'
}
# 定义MongoDB属性
MONGO_URL = 'localhost'
MONGO_DB = 'toutiao'
MONGO_TABLE = 'toutiao'

# 定义起始循环条件
GROUP_START = 1
# 定义终止循环条件
GROUP_END = 20

client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]


# 仅供测试
def Xie_Ru(content):
    with open('result.txt', 'a', encoding='utf-8') as f:
        # 将字典转换成字符串
        string = json.dumps(content, ensure_ascii=False)
        # 写入并增加换行符
        f.write(string + '\n')


# 构造Ajax请求，获取HTML代码
def get_pages(offset):
    # 添加url参数
    params = {
        'aid': '24',
        'app_name': 'web_search',
        'offset': offset,
        'format': 'json',
        'keyword': '街拍',
        'autoload': 'true',
        'count': 20,
        'en_qc': 1,
        'cur_tab': 1,
        'from': 'search_tab',
        'pd': 'synthesis',
        # 'timestamp':1553221825584
        # 'timestamp':1553319072026
    }

    base_url = 'https://www.toutiao.com/api/search/content/?keyword=%E8%A1%97%E6%8B%8D'
    url = base_url + urlencode(params)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except requests.ConnectionError as e:
        print('Error', e.args)


# 获取详情页里Jason里的文章的url
def parse_page_index(html):
    if html and 'data' in html.keys():
        for item in html.get('data'):
            if item.get('cell_type') == None and item.get('article_url')[7:14] == 'toutiao':
                yield item.get('article_url')


# 通过url获取详情页源码
def get_page_detail(url):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # 测试是否读到网页源代码
            # Xie_Ru(response.text)
            # 返回文章的网页源码
            return response.text
    except RequestException:
        print('Error', url)


# 解析详情页源码,取出图片url
def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    # 获取“[<title>陈数难得街拍一回，穿牛仔裤堪比24岁少女，看不出42岁</title>]”，一个元素的数组
    title_1 = soup.select('title')
    # 获取数组里面的文字信息，即文章标题
    title = title_1[0].get_text()
    # 使用正则表达式获取图片地址
    images_pattern = re.compile('[a-zA-z]+://[^\s]*&quot', re.S)
    result = re.findall(images_pattern, html)
    # 构造url数组
    images = [i[:-5] for i in result]
    for image in images:
        download_image(image, title)
    # print(images)
    return {
        'title': title,
        'url': url,
        'images': images
    }


# 保存图片和其url到MongoDB
def save_to_mongo(result):
    # 判断是否成功插入
    if db[MONGO_TABLE].insert(result):
        print('成功存储到MongoDB', result)
        return True
    return False


# 根据图片url下载图片
def download_image(url, title):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # return response.text返回网页内容，请求网页用
            # response.content返回文件二进制内容，获取图片用
            save_image(response.content, title)
            print('正在下载', url)
    except RequestException:
        print('请求图片出错', url)


# 将图片保存到本地
def save_image(content, title):
    # 创建文件夹保存图片
    image_path = '街拍' + '/' + title
    if not os.path.exists(image_path):
        os.makedirs(image_path)
    # 构造文件保存路径到当前路径下,并检测文件内容是否重复，保存成‘jpg’格式
    # 根据图片计算出MD5值作为文件名。（MD5可以保证唯一性）
    file_path = '{0}/{1}.{2}'.format(image_path, md5(content).hexdigest(), 'jpg')
    # 当前路径下不存在此文件夹则创建
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as picture:
            picture.write(content)


# 主函数
def main(offset):
    html = get_pages(offset)
    for url in parse_page_index(html):
        # print(url)
        # get_page_detail(url)
        html = get_page_detail(url)
        r = parse_page_detail(html, url)
        # print(r)
        save_to_mongo(r)
        '''
        with open('url.txt','a',encoding='utf-8') as a:
                a.write(str(url)+'\n')
        '''


if __name__ == '__main__':
    # 创建一个offset集合
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    # 创建一个进程池对象
    pool = Pool()
    # 开启多进程
    pool.map(main, groups)
