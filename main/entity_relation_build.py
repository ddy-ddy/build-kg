# -*- coding: utf-8 -*-
# @Time    : 2022/2/4 7:44 下午
# @Author  : ddy
# @FileName: entity_relation_build.py
# @github  : https://github.com/ddy-ddy

from util import *
from definitions import *
from tqdm import tqdm
import spacy


class build_kg():
    nlp = spacy.load('en_core_web_md')
    all_nodes, all_relations = [], []  # 所有节点和关系
    temp_nodes = []  # 临时存放信息的节点
    data_type = ["byte", "int", "integer", "float", "char", "boolean", "double", "long", "short"]

    def __init__(self):
        self.data = get_data_from_json(build_kg_data_DIR + "api_semantic_syntax_label_info.json")

    def execute(self):
        id = 0  # 节点的id
        for _, info in enumerate(tqdm(self.data)):
            nodes, relations = [], []  # 当前description拥有的节点和关系
            d_o_flag, p_o_flag = False, False  # 判断是否有direct_object和preposition_object

            ########### 添加节点
            '''
            {
                "id"
                "name"
                "search_id"
                "type"
                "info"
            }
            '''
            # 添加api_method节点
            api_method_node = {"name": info["api_method"], "type": "api_method"}
            api_method_node, id, nodes = self.add_node(api_method_node, id, None, nodes)

            # 添加action节点
            action_name = " ".join([info["syntax_label"]["verb"], info["syntax_label"]["particle"]])
            action_node = {"name": action_name.strip(), "type": "action"}
            action_node, id, nodes = self.add_node(action_node, id, None, nodes)

            # 添加participant节点
            if info["syntax_label"]["direct_object"]:
                d_o_flag = True
                direct_object_node = {"name": info["syntax_label"]["direct_object"], "type": "participant"}
                direct_object_node, id, nodes = self.add_node(direct_object_node, id, None, nodes)
            if info["syntax_label"]["preposition_object"]:
                p_o_flag = True
                preposition_object_node = {"name": info["syntax_label"]["preposition_object"],
                                           "type": "participant"}
                preposition_object_node, id, nodes = self.add_node(preposition_object_node, id, None,
                                                                   nodes)

            # 添加event节点
            if d_o_flag:  # action+d_o
                event_name = " ".join([info["syntax_label"]["verb"], info["syntax_label"]["direct_object"]])
                event_info = {"action": action_node["search_id"], "direct_object": direct_object_node["search_id"]}
                event_node = {"name": event_name, "type": "event"}
                event_node, id, nodes = self.add_node(event_node, id, event_info, nodes)

            elif not d_o_flag and p_o_flag:  # action+prep+p_o
                event_name = " ".join([info["syntax_label"]["verb"], info["syntax_label"]["preposition"],
                                       info["syntax_label"]["preposition_object"]])
                event_info = {"action": action_node["search_id"],
                              "preposition_object_node": preposition_object_node["search_id"]}
                event_node = {"name": event_name, "type": "event"}
                event_node, id, nodes = self.add_node(event_node, id, event_info, nodes)
            else:
                print("not exist event")

            # 添加事件约束节点
            event_constraint = []
            for argm in list(info["argm_label"].keys()):
                event_constraint_node = {"name": info["argm_label"][argm], "type": "event_constraint"}
                event_constraint_node, id, nodes = self.add_node(event_constraint_node, id, None, nodes)
                event_constraint.append({argm: event_constraint_node})

            # 添加事件参与者约束节点
            d_o_constraint = info["syntax_label"]["direct_object_modifiers"]
            p_o_constraint = info["syntax_label"]["preposition_object_modifiers"]
            if d_o_flag and d_o_constraint:
                direct_object_constraint = []
                for constraint in d_o_constraint:
                    participant_constraint_node = {"name": constraint, "type": "participant_constraint"}
                    participant_constraint_node, id, nodes = self.add_node(participant_constraint_node, id, None, nodes)
                    direct_object_constraint.append(participant_constraint_node)
            if p_o_flag and p_o_constraint:
                preposition_object_constraint = []
                for constraint in d_o_constraint:
                    participant_constraint_node = {"name": constraint, "type": "participant_constraint"}
                    participant_constraint_node, id, nodes = self.add_node(participant_constraint_node, id, None, nodes)
                    preposition_object_constraint.append(participant_constraint_node)

            ########### 添加功能性关系
            '''
            (node1,relation_name,relation_info,node2)
            '''
            # Has_Action
            relations.append((api_method_node["search_id"], "Has_Action", None, action_node["search_id"]))
            # Has_Event
            relations.append((api_method_node["search_id"], "Has_Event", None, event_node["search_id"]))
            relations.append((action_node["search_id"], "Has_Event", None, event_node["search_id"]))
            # Has_Direct_Object
            if d_o_flag:
                relations.append((event_node["search_id"], "Has_Direct_Object", None, direct_object_node["search_id"]))
            # Has_Preposition_Object
            if p_o_flag:
                relations.append(
                    (event_node["search_id"], "Has_Preposition_Object", info["syntax_label"]["preposition"],
                     preposition_object_node["search_id"]))

            ########### 添加修饰性关系
            # 事件与事件约束之间的关系
            for constraint in event_constraint:
                keys = list(constraint.keys())[0]
                value = constraint[keys]
                relation_name = self.change_argm_relation(keys)  # 将argm与自定义的关系进行映射
                relations.append((event_node["search_id"], relation_name, None, value["search_id"]))
            # 参与者与参与者约束之间的关系
            if d_o_flag and d_o_constraint:
                for constraint in direct_object_constraint:
                    relation_name = self.classify_participant_constraint_type(info["description"], constraint["name"])
                    relations.append((direct_object_node["search_id"], relation_name, None, constraint["search_id"]))
            if p_o_flag and p_o_constraint:
                for constraint in preposition_object_constraint:
                    relation_name = self.classify_participant_constraint_type(info["description"], constraint["name"])
                    relations.append(
                        (preposition_object_node["search_id"], relation_name, None, constraint["search_id"]))

            # 补充api_method节点的信息
            relations = list(set(relations))  # 为relations去重
            api_method_node["info"] = relations
            api_method_node["description"] = info["description"]
            self.all_nodes[api_method_node["search_id"]] = api_method_node

            # 添加该description所有关系至关系库中
            self.all_relations.extend(relations)

        # 保存所有信息
        self.save_info()

    def classify_participant_constraint_type(self, description: str, constraint: str) -> str:
        '''
        为参与者约束进行分类
        1.Has_Status: 修饰语为形容词
        2.Has_Type: 修饰语为名词或内置数据类型
        内置数据类型：["byte","int/integer","float","char","boolean","double","long","short"]
        :param description:
        :param constraint:
        :return:
        '''
        doc = self.nlp(description)
        for token in doc:
            if token.text == constraint:
                if token.pos_ in ["ADJ", "VERB", "NUM", "ADV"]:
                    return "Has_Status"
                elif token.pos_ in ["NOUN", "PROPN"] or token.text in self.data_type:
                    return "Has_Type"
                else:
                    print("not match")
                    return "Has_Status"
        else:
            print("not have name")
            return "Has_Status"

    def change_argm_relation(self, argm: str) -> str:
        '''
        将argm与自定义的关系进行映射
        :return:
        '''
        if argm == "ARGM-LOC":
            return "Has_Location"
        elif argm == 'ARGM-DIR':
            return "Has_Direction"
        elif argm == 'ARGM-MNR':
            return "Has_Manner"
        elif argm == 'ARGM-EXT':
            return "Has_Extent"
        elif argm == 'ARGM-TMP':
            return "Has_Temporal"
        elif argm == 'ARGM-GOL':
            return "Has_Goal"
        elif argm == 'ARGM-PRP':
            return "Has_Purpose"
        elif argm == 'ARGM-PRD':
            return "Has_Result"
        elif argm == 'ARGM-ADV':
            return "Has_Constraint"
        else:
            print(argm)

    def save_info(self):
        dump_dict_to_json_file(build_kg_data_DIR + "all_node_info.json", self.all_nodes)
        dump_dict_to_json_file(build_kg_data_DIR + "all_relation_info.json", self.all_relations)

        node_data = pd.DataFrame({":ID": [item["id"] for item in self.all_nodes],
                                  ":label": [item["type"] for item in self.all_nodes],
                                  "name": [item["name"] for item in self.all_nodes],
                                  "search_id": [item["search_id"] for item in self.all_nodes],
                                  "info": [str(item["info"]) for item in self.all_nodes]
                                  })
        relation_data = pd.DataFrame({":START_ID": [item[0] for item in self.all_relations],
                                      ":TYPE": [item[1] for item in self.all_relations],
                                      "preposition_name": [item[2] for item in self.all_relations],
                                      ":END_ID": [item[3] for item in self.all_relations]
                                      })
        node_data = node_data.drop_duplicates()
        relation_data = relation_data.drop_duplicates()
        node_data.to_csv(build_kg_data_DIR + "node.csv", index=False)
        relation_data.to_csv(build_kg_data_DIR + "relation.csv", index=False)

    def add_node(self, node, id, node_property_info, nodes):
        '''

        :param node: 要添加的节点
        :param id: 当前节点id号
        :param node_property_info: 要添加的节点的info属性信息
        :param nodes: 当前description所拥有的节点
        :return:
        '''
        # 如果该节点不存在所有节点中时
        if node not in self.temp_nodes:
            temp = node.copy()
            self.temp_nodes.append(temp)
            node["search_id"] = id
            node["id"], id = id, id + 1
            node["info"] = node_property_info
            self.all_nodes.append(node)
            nodes.append(node)
        else:
            node = self.all_nodes[self.temp_nodes.index(node)]
            nodes.append(node)
        return node, id, nodes


if __name__ == '__main__':
    build_kg().execute()
