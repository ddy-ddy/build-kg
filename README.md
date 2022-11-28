## 基于语法语义角色标注模型构建api知识图谱

- 爬取并处理Java文档中约5万条API数据
- 对数据进行预处理和分析，根据分析的数据设计知识图谱的实体和关系
- 使用SpaCy搭建基于语法语义依存树的数据标注模型，自动的从数据中抽取实体和关系
- 利用 Neo4j 图数据库构建API知识图谱



## Step1：收集数据并分析

##### 数据来源：[java document](https://docs.oracle.com/javase/8/docs/api/)

##### 数据字段组成

| 字段名                    | 详细介绍                                         |
| ------------------------- | ------------------------------------------------ |
| qualified_name            | java api method全称                              |
| functionality_description | java api method的功能性描述，取api描述的第一句话 |

##### 数据展示

![](https://tva1.sinaimg.cn/large/e6c9d24egy1gzufjehqqzj20zz0cwtdb.jpg)



## 2、定义实体和关系

##### 实体

| 实体类型               | 详细描述                                     |
| ---------------------- | -------------------------------------------- |
| api_method             | api method实体                               |
| action                 | 功能性描述的主要动作                         |
| participant            | 功能性描述的参与者，分别为直接宾语和介词宾语 |
| event                  | action+participant                           |
| event_constraint       | event实体的约束                              |
| participant_constraint | participant实体的约束                        |

##### 关系

| 前序实体类型 | 关系                   | 后继实体类型 |
| ------------ | ---------------------- | ------------ |
| api_method   | Has_Action             | action       |
| api_method   | Has_Event              | event        |
| api_method   | Has_Event              | action_event |
| event        | Has_Direct_Object      | participant  |
| event        | Has_Preposition_Object | participant  |



## Step3：从数据中自动抽取实体和关系

##### 目的：从功能性描述中自动抽取出上述定义的实体, 然后再根据上述规则构建关系

##### Step1：对功能性描述进行语义角色标注

- 使用Allennlp的semantic role labeling模型对功能性描述进行标注，输入句子，输出语义标注结果 | [allenlp工具](https://demo.allennlp.org/semantic-role-labeling)

- 将V+ARG1+ARG2...ARG4组成新的句子【称作api描述的主要功能】，ARGM-...则构成event_constraint实体 | [语义角色标准使用propbank标准](http://clear.colorado.edu/compsem/documents/propbank_guidelines.pdf)

<img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzug50v2oij215g04eq3q.jpg" style="zoom:40%;" />

##### Step2：对api描述的主要功能进行语法角色标注

- 基于Spacy对主要功能进行语法角色标注，得到至多6种语法角色 | 参考论文1 | [Spacy工具🔗](https://spacy.io/)

- 将提取到的语法角色与定义的实体进行对应

<img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzugd6383zj21yy0k4jtd.jpg" style="zoom:30%;" />

| <img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzugea7fq2j20wy0g8di9.jpg" style="zoom:30%;" /> | <img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzughj2hvsj20q60eo3zy.jpg" style="zoom:38%;" /> |
| :----------------------------------------------------------: | :----------------------------------------------------------: |

##### Step3：根据抽取到的信息构建实体和关系，最终构建KG

- 实体在上述信息抽取过程已经对应完毕，接着根据Step2提到的三元组构建关系，最终得到node.csv和relation.csv

| <img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzugpotbrzj20da071gm5.jpg" style="zoom:70%;" /> | <img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzugpnepf9j20df074gm2.jpg" style="zoom:70%;" /> |
| :----------------------------------------------------------: | :----------------------------------------------------------: |



## 4、将数据导入Neo4j并可视化

##### 将node.csv和relation.csv导入neo4j中，使用neo4j import导入数据，数据比较大时，使用import可以大大降低导入时间

```shell
./bin/neo4j-admin import --nodes "node.csv" --relationships "relation.csv"
```

##### 知识图谱展示

<img src="https://tva1.sinaimg.cn/large/e6c9d24egy1gzuh2pzs18j21rf0u0agd.jpg" style="zoom:50%;" />



## 5、项目目录

```shell
├── LICENSE
├── README.md
├── data
├── definitions.py #定义路径
├── import2neo4j   #将数据导入到neo4j
│   └── neo4j-import
│       ├── bin
│       ├── import
│       ├── import.report
│       ├── import.sh                   #将输入导入到neo4j脚本
│       ├── lib
│       ├── logs
│       ├── run
│       └── run.sh                      #打开neo4j脚本
├── main  #构建KG代码
│   ├── entity_relation_build.py        #将抽取到的信息对应到实体与关系
│   ├── pipeline.py                     #从句子中抽取信息的代码
│   ├── run.py                          #入口
│   └── util.py                         #数据读取相关的函数
├── output
│   ├── build_kg_data                   #存储kg相关的数据
│   └── crawl_data                      #存储原始数据
├── requirements.txt                  
└── util_model                          #使用的semantic role labeling模型
    └── structured-prediction-srl-bert.2020.12.15
```



## 6、参考文献

​    Treude, C., Robillard, M. P. & Dagenais, B. Extracting Development Tasks to Navigate Software Documentation. *Ieee T Software Eng* **41**, 565–581 (2014).  

