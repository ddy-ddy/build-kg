import os

'''
对于整个项目级别的一些常量进行定义，方便其他地方引用。
注意：在代码中千万不要使用绝对路径，要使用基于ROOT_DIR的相对路径
'''

# Path_name
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))  # This is your Project Root

extract_tasks_DIR = ROOT_DIR + "/data/extract_tasks/"
crawl_data_DIR = ROOT_DIR + "/output/crawl_data/"
build_kg_data_DIR = ROOT_DIR + "/output/build_kg_data/"
interact_data_DIR = ROOT_DIR + "/output/interact_data/"
biker_data_DIR = ROOT_DIR + "/data/biker_data/"
data_DIR = ROOT_DIR + "/data/"
