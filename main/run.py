# -*- coding: utf-8 -*-
# @Time    : 2022/2/4 7:14 下午
# @Author  : ddy
# @FileName: run.py
# @github  : https://github.com/ddy-ddy

from util import *
from definitions import *
from tqdm import tqdm
# from pipeline import Information_Extraction
from entity_relation_build import build_kg


def add_api_method_info():
    '''
    将api信息加入到信息中
    :return:
    '''
    api_data = pd.read_csv(crawl_data_DIR + "original_data.csv")
    label_info = get_data_from_json(build_kg_data_DIR + "after_semantic_syntax_label_info.json")

    api_method = list(api_data.qualified_name)
    functionality_description = list(api_data.functionality_description)
    desc_index = [item["description"] for item in label_info]

    result_info = []
    for i, api in enumerate(tqdm(api_method)):
        desc = functionality_description[i]
        if desc in desc_index:
            index = desc_index.index(desc)
            temp_info = label_info[index]
            temp_info["api_method"] = api
            add_info=temp_info.copy()
            result_info.append(add_info)

    dump_dict_to_json_file(build_kg_data_DIR + "api_semantic_syntax_label_info.json", result_info)


def build_search_id_to_node_info(path, json_data):
    save_info = {}
    for item in json_data:
        save_info[item["search_id"]] = item
    dump_dict_to_json_file(path, save_info)


def build_kg_by_all_information():
    # 提取所有的信息
    # Information_Extraction().extract_all_information()

    # 添加api_method_info
    add_api_method_info()

    # build kg
    build_kg().execute()

    # 构建索引字典
    data = get_data_from_json(build_kg_data_DIR + "all_node_info.json")
    build_search_id_to_node_info(interact_data_DIR + "search.json", data)


if __name__ == '__main__':
    build_kg_by_all_information()
    # add_api_method_info()