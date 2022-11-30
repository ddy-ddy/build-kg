#删除数据库
rm -rf ./data/databases

#导入
./bin/neo4j-admin import --nodes "../../output/build_kg_data/node.csv" --relationships "../../output/build_kg_data/relation.csv"

cd ./bin

#运行neo4j
./neo4j restart