import os
import sys
import requests
from bs4 import BeautifulSoup
import imghdr
import marko
import html2text

def download_image(image_url, save_path, save_name):
    response = requests.get(image_url)
    image_data = response.content

    # 根据响应内容确定图片的格式
    image_format = imghdr.what(None, image_data)
    if image_format is None:
        # 如果无法确定图片格式，则根据URL中的文件扩展名来确定
        image_format = os.path.splitext(image_url)[1][1:].lower()

    # 生成保存图片的文件路径
    image_filename = f"image-{save_name}.{image_format}"
    save_path = os.path.join(save_path, image_filename)

    # 保存图片
    with open(save_path, 'wb') as file:
        file.write(image_data)
    return save_path, save_name

def process_markdown_file(md_file):
    # 获取文件名和目录
    file_name = os.path.basename(md_file)
    file_dir = os.path.dirname(md_file)
    images_dir = os.path.join(file_dir, f"images-{file_name[:-3]}")

    # 创建图片目录
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    # 读取Markdown文件内容
    with open(md_file, 'r', encoding='utf-8') as file:
        content = file.read()

    # 使用BeautifulSoup解析Markdown内容
    # soup = BeautifulSoup(content, 'html.parser')
    soup = BeautifulSoup(marko.convert(content))
    # 查找所有的图片链接
    image_tags = soup.find_all('img')
    for index, image_tag in enumerate(image_tags):
        image_url = image_tag['src']

        # 从图片链接中提取文件名
        save_path, save_name = download_image(image_url, images_dir, index)

        image_tag['src'] = save_path
        image_tag['alt'] = save_name
    
    # 将BeautifulSoup对象转换为Markdown格式
    md_converter = html2text.HTML2Text()
    md_converter.body_width = 0  # 设置行宽度，0表示不限制
    markdown = md_converter.handle(soup.prettify())

    # 将修改后的内容写回Markdown文件
    with open("res_" + md_file, 'w', encoding='utf-8') as file:
        file.write(str(markdown))

if __name__ == "__main__":
    # 通过argparse模块解析命令行参数
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", required=True, help="Markdown文件路径")
    args = parser.parse_args()
    markdown_file = args.f
    process_markdown_file(markdown_file)