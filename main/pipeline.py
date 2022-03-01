# -*- coding: utf-8 -*-
# @Time    : 2022/2/11 8:52 上午
# @Author  : ddy
# @FileName: pipeline.py
# @github  : https://github.com/ddy-ddy

import re
from lemminflect import getLemma, getInflection
from allennlp.predictors.predictor import Predictor
from definitions import *
from typing import List, Tuple
from nltk import tokenize
from simplenlg import *
import spacy
from spacy.matcher import DependencyMatcher
from util import *
from tqdm import tqdm

# set spacy
nlp = spacy.load("en_core_web_md")
# set SRL model
path = ROOT_DIR + "/project/util_model/structured-prediction-srl-bert.2020.12.15"
predictor = Predictor.from_path(path)


class parse_functionality_description(object):
    object_prepositions = ["of"]

    def __init__(self, rules_dir=extract_tasks_DIR):
        self.nlp = nlp
        with open(os.path.join(rules_dir, "coderegex.txt"), "r") as c_file:
            self.regexes = [line.strip() for line in c_file if line.strip()]
        with open(os.path.join(rules_dir, "domain.txt"), "r") as d_file:
            self.domain_terms = [line.strip() for line in d_file if line.strip()]
        with open(os.path.join(rules_dir, "filtered_verbs.txt"), "r") as v_file:
            self.filtered_verbs = [line.strip() for line in v_file if line.strip()]
        with open(os.path.join(rules_dir, "generics.txt"), "r") as g_file:
            self.generic_terms = set([line.strip() for line in g_file if line.strip()])
        self.filtered_verb_lemmas = set([getLemma(verb, "VERB")[0] for verb in self.filtered_verbs])

    def extract_task_trees(self, docstrings: List[str]):
        """Extracts task trees from a docstring
        Args:
            docstring:
        Returns
        """
        for docstring in docstrings:
            sentences = self.preprocess_docstring(docstring)
            sentences, replacements = self.format_sentences(sentences)
            dependencies = self.extract_dependencies(sentences)
            task_trees = self.create_trees(dependencies, replacements)
            yield task_trees

    def extract_task_dicts(self, docstrings: List[str]):
        """Extracts task trees from a docstring

        Args:
            docstring:

        Returns
        """
        for docstring in docstrings:
            if not docstring:
                yield []
                continue
            sentences = self.preprocess_docstring(docstring)
            sentences, replacements = self.format_sentences(sentences)
            dependencies = self.extract_dependencies(sentences)
            if not dependencies:
                yield []
                continue
            task_dicts = self.create_dicts(dependencies, replacements)
            yield task_dicts

    def preprocess_docstring(self, docstring: str) -> List[str]:
        """Splits docstring into sentences and processes text for task analysis

        Args:
            docstring (str): A function's docstring.

        Returns:
            Tuple[List[str], List[List[str]]]: Tuple containing the list of
            processed sentences alongside a parallel list of OOV/domain-specific
            tokens substituted in each sentence

        """
        docstring = self._remove_docstring_formatting(docstring)
        sentences = self._split_sentences(docstring)
        return [s.strip() for s in sentences if s.strip()]

    def _split_sentences(self, docstring: str) -> List[str]:
        """Splits docstrings into on newlines and relevant punctuation.
        """
        sentences = []

        sections = docstring.split("\n\n")
        for section in sections:
            lines = section.split("\n")
            sentence = ""
            num_space = 0
            for line in lines:
                new_num_space = len(re.split("\S", line)[0].replace("\t", "    "))
                line = line.strip()
                if line.startswith("@"):
                    if sentence:
                        sentences += tokenize.sent_tokenize(sentence)
                        sentence = ""
                    if len(line.split()) > 2:
                        sentence = line.split(maxsplit=2)[-1].strip()
                elif line:
                    sentence += " " + line
                num_space = new_num_space
            if sentence:
                sentences += tokenize.sent_tokenize(sentence)
        return sentences

    def _remove_docstring_formatting(self, docstring) -> str:
        """Removes special formatting text from docstrings

        For instance, text like "{@link Foo}" is replaced with "Foo".
        We're assuming that this formatting information will not be used
        for downstream tasks.
        """
        # Java formatting {@class term} -> term
        docstring = re.sub(r"\{@\w+?\s+?#*(.*?)\}", r"\1", docstring)
        # Python formatting :attr:`(term)` -> term
        docstring = re.sub(r"\:\w+?\:\`(.*?)\`", r"\1", docstring)
        docstring = re.sub(r"\n\W*?\:\w+?\:\`(.*?)\`", r"\n\n\1", docstring)
        # Python formatting \n:attr (term): -> term
        docstring = re.sub(r"\n\W*?\:.+?\:", "\n\n", docstring)
        docstring = re.sub(r"<(\S+?)>", "", docstring)
        return docstring

    def format_sentences(self, sentences: list) -> Tuple[List[str], List[List[str]]]:
        """Prepares docstring sentences for task extraction.
        """
        # Stage 1: add periods/split sentences and remove parentheticals
        for i, sentence in enumerate(sentences):
            if sentence[-1] not in [".", "!", "?"]:
                sentence += "."
            for match in re.finditer(r"\W\(.+?\)\W", sentence):
                term = match[0].strip()
                sentences[i] = sentence.replace(term, "")
        # Stage 2: Replace regular expressions with generic token
        sentence_replacements = [[] for _ in sentences]
        for regex_str in self.regexes:
            for i, sentence in enumerate(sentences):
                for match in re.finditer(rf"{regex_str}", sentences[i]):
                    n = len(sentence_replacements[i])
                    term = match[0].strip()
                    if term and "rep_item" not in term:
                        sentence_replacements[i].append(term)
                        sentences[i] = re.sub(rf"{re.escape(term)}", f" rep_item_{n} ", sentences[i])
        for domain_term in self.domain_terms:
            for i, sentence in enumerate(sentences):
                for match in re.finditer(rf"\b{domain_term}\b", sentences[i]):
                    n = len(sentence_replacements[i])
                    term = match[0].strip()
                    if term and "rep_item" not in term:
                        sentence_replacements[i].append(term)
                        sentences[i] = re.sub(rf"\b{re.escape(term)}\b", f"rep_item_{n}", sentences[i])
        # Step 3: Add "For"/"This" as needed based on initial word in sentence.
        for i, sentence in enumerate(sentences):
            tokens = sentence.split()
            firstword = tokens[0].lower()
            secondword = tokens[1].lower() if len(tokens) > 2 else ""

            if firstword in ["function", "method"] and secondword == "to":
                sentences[i] = sentence.split(secondword, 1)[1]
            #             if firstword in self.verbs_vbz:
            #                 sentences[i] = "This " + sentence[0].lower()+sentence[1:]
            #             elif firstword in self.verbs_vbg:
            #                 sentences[i] = "For " + sentence[0].lower()+sentence[1:]
            #             else:
            # # Code to get lemmas for OOV words
            # if not getAllLemmas(firstword):
            #     lemmas = getLemma(firstword, "VERB")
            # else:
            lemmas = getLemma(firstword, "VERB", lemmatize_oov=False)
            for lemma in lemmas:
                vbz = getInflection(lemma, tag="VBZ", )
                vbg = getInflection(lemma, tag="VBG")
                if firstword in vbz:
                    sentences[i] = "This " + sentence[0].lower() + sentence[1:]
                    break
                elif firstword in vbg:
                    sentences[i] = "For " + sentence[0].lower() + sentence[1:]
                    break
        sentences = [sentence.lower() for sentence in sentences]
        sentences = [" ".join(s.split()) for s in sentences]
        return (sentences, sentence_replacements)

    def _is_acceptable_object_preposition(self, prep_word):
        if prep_word in self.object_prepositions:
            return True
        else:
            return False

    def extract_dependencies(self, sentences):
        dependencies = []
        for sentence in sentences:
            doc = self.nlp(sentence)
            # Find all verbs in the doc
            matcher = DependencyMatcher(self.nlp.vocab)
            verb_pattern = [
                {
                    "RIGHT_ID": "verb",
                    "RIGHT_ATTRS": {"POS": "VERB"}
                }
            ]
            matcher.add("VERB", [verb_pattern])
            verb_matches = matcher(doc)
            verbs = [doc[match[1][0]] for match in verb_matches]
            # Trace relevant dependencies for each verb
            sentence_dependencies = []
            for verb in verbs:
                #                 if getLemma(verb.text, "VERB")[0] not in self.verb_lemmas:
                if getLemma(verb.text, "VERB")[0] in self.filtered_verb_lemmas:
                    continue
                neg = None
                prt = None
                objs = []
                preps = []
                objpreps = defaultdict(list)

                # Get all objects and prepositions for verb
                for child in verb.children:
                    if child.dep_ == "neg":
                        neg = child
                    elif child.dep_ == "prt":
                        prt = child
                    elif child.dep_ == "prep":
                        preps.append(child)
                    elif child.dep_ in ["dobj", "nsubjpass"]:
                        objs.append(child)
                        for obj_child in child.children:
                            if obj_child.dep_ == "prep" and not self._is_acceptable_object_preposition(obj_child.text):
                                preps.append(obj_child)

                if verb.dep_ == "relcl":
                    if not (verb.head.dep_ == "pobj" and verb.head.head.text == "of"):
                        objs.append(verb.head)

                # Separate compound objects and prepositions
                objs += [conjunct for obj in objs for conjunct in obj.conjuncts]
                preps += [conjunct for prep in preps for conjunct in prep.conjuncts]

                # Create all task tuples with as much detail as possible
                verb_tuple = (verb,)
                if prt: verb_tuple = verb_tuple + (prt,)
                # if neg: verb_tuple = verb_tuple+(neg,)
                if objs:
                    for obj in objs:
                        if preps:
                            for prep in preps:
                                sentence_dependencies.append(verb_tuple + (obj, prep))
                        else:
                            sentence_dependencies.append(verb_tuple + (obj,))
                elif preps:
                    for prep in preps:
                        sentence_dependencies.append(verb_tuple + (prep,))
            dependencies.append(sentence_dependencies)
        return dependencies

    def create_dicts(self, dependencies, sentence_replacements):
        def is_acceptable(object_word):
            if (object_word.lower() not in self.generic_terms
                    and re.search('[a-zA-Z]', object_word) is not None
                    and len(object_word) > 1):
                return True
            else:
                return False

        def recoverWord(token, replacement_idx):
            if token.text.startswith("rep_item_"):
                t = token.text.split("_")[-1]
                i = int(re.split(r'\D+', t)[0])
                return sentence_replacements[replacement_idx][i].strip().rstrip(",.")
            else:
                return token.text.strip().rstrip(",.")

        def processObject(obj_token, i):
            obj_dict = {
                "object_det": "",
                "object": "",
                "object_modifiers": [],
            }
            # Check if child is generic, and if so, skip
            obj_word = recoverWord(obj_token, i)
            compound_words = ""
            if is_acceptable(obj_word):
                obj_dict["object"] = obj_word
                # If child is noun, process noun phrase and add
                # if obj_token.pos_ == "NOUN":
                for obj_child in obj_token.children:
                    modifier_word = recoverWord(obj_child, i)
                    if obj_child.dep_ == "det":
                        obj_dict["object_det"] = modifier_word
                    elif obj_child.dep_ in ["compound", "nmod"]:
                        compound_word = ""
                        compounds = [obj_child]
                        while compounds:
                            current_compound_obj = compounds.pop(0)
                            current_compount_word = recoverWord(current_compound_obj, i)
                            if current_compound_obj.dep_ in ["compound", "nmod"] and is_acceptable(
                                    current_compount_word):
                                compound_word = f"{current_compount_word} {compound_word}".strip()
                                for compound_child in current_compound_obj.children:
                                    compounds.insert(0, compound_child)
                        compound_words = f"{compound_words} {compound_word}".strip()
                    elif obj_child.dep_ in ["amod", "nummod"] and is_acceptable(modifier_word):
                        obj_dict["object_modifiers"].append(modifier_word)
                    elif obj_child.dep_ == "prep":
                        prep_word = obj_child.text
                        if self._is_acceptable_object_preposition(prep_word):
                            prep_children = [t for t in obj_child.children]
                            while prep_children and prep_children[0].dep_ == "prep":
                                prep_word = " ".join([prep_word, prep_children[0].text])
                                prep_children = [t for t in prep_children[0].children]
                            if len(prep_children) >= 1:
                                prep_obj_dict = processObject(prep_children[0], i)
                                if prep_obj_dict:
                                    prep_obj_word = prep_obj_dict["object"]
                                    if prep_obj_dict["object_modifiers"]:
                                        prep_obj_modifiers = " ".join(prep_obj_dict["object_modifiers"])
                                        prep_obj_word = " ".join([prep_obj_modifiers, prep_obj_word])
                                    if prep_obj_dict["object_det"]:
                                        prep_obj_word = " ".join([prep_obj_dict['object_det'], prep_obj_word])
                                    obj_dict["object"] = " ".join([obj_dict['object'], prep_word, prep_obj_word])
                obj_dict["object"] = f"{compound_words} {obj_dict['object']}".strip()
            if obj_dict["object"]:
                return obj_dict
            else:
                return None

        # Step 1: Import generic terms and domain verbs
        #         use_domain_verbs = True

        # Step 1.5: Filter out not-in-domain verbs
        #         if use_domain_verbs:
        #             for i, sentence_dependencies in enumerate(dependencies):
        #                 filtered_sentence_dependencies = []
        #                 for j, dependency_tuple in enumerate(sentence_dependencies):
        #                     verb = recoverWord(dependency_tuple[0], i)
        #                     lemma = getLemma(verb, "VERB")[0]
        #                     if lemma in self.verb_lemmas:
        #                         filtered_sentence_dependencies.append(dependency_tuple)
        #                 dependencies[i] = filtered_sentence_dependencies

        # Step 2: Create trees, filtering out generic terms and incomplete tasks
        task_dicts = []
        for i, sentence_dependencies in enumerate(dependencies):
            sentence_task_dicts = []
            for j, dependency_tuple in enumerate(sentence_dependencies):
                # Extract all children of top-level verb phrase
                task_dict = {
                    "verb": "",
                    "particle": "",
                    "direct_object_det": "",
                    "direct_object": "",
                    "direct_object_modifiers": [],
                    "preposition": "",
                    "preposition_object_det": "",
                    "preposition_object": "",
                    "preposition_object_modifiers": [],
                }
                task_dict["verb"] = recoverWord(dependency_tuple[0], i)
                for token in dependency_tuple[1:]:
                    token_word = recoverWord(token, i)

                    # 1. Prepositions
                    # Leave out if prep. object is generic term
                    # Otherwise, leave out any generic modifiers
                    if token.dep_ == "prep":
                        prep_word = token.text
                        token_children = [t for t in token.children]
                        while token_children and token_children[0].dep_ == "prep":
                            prep_word = " ".join([prep_word, token_children[0].text])
                            token_children = [t for t in token_children[0].children]
                        if len(token_children) >= 1:
                            prep_obj_dict = processObject(token_children[0], i)
                            if prep_obj_dict:
                                task_dict["preposition"] = prep_word
                                task_dict["preposition_object"] = prep_obj_dict["object"]
                                task_dict["preposition_object_modifiers"] = prep_obj_dict["object_modifiers"]
                                task_dict["preposition_object_det"] = prep_obj_dict["object_det"]
                    # 2: Direct objects
                    # Leave out if direct object is generic term
                    # Otherwise, leave out any generic modifiers
                    else:
                        direct_obj_dict = processObject(token, i)
                        if direct_obj_dict:
                            task_dict["direct_object"] = direct_obj_dict["object"]
                            task_dict["direct_object_modifiers"] = direct_obj_dict["object_modifiers"]
                            task_dict["direct_object_det"] = direct_obj_dict["object_det"]
                if task_dict["preposition_object"] or task_dict["direct_object"]:
                    sentence_task_dicts.append(task_dict)
            task_dicts.append(sentence_task_dicts)
        return task_dicts

    def parse_task_trees(self, task_trees):
        for sentence_task_trees in task_trees:
            for sentence_task_tree in sentence_task_trees:
                tokens = sentence_task_tree.leaves()
                verb = tokens[0]
                lemma = getLemma(verb, "VERB")[0]
                verb = getInflection(lemma, "VB")[0]
                tokens[0] = verb
                task = " ".join(tokens)
                yield task

    def parse_task_dicts(self, task_dicts):
        for sentence_task_dicts in task_dicts:
            for task_dict in sentence_task_dicts:
                lemma = getLemma(task_dict["verb"], "VERB")[0]
                verb = getInflection(lemma, "VB")[0]
                tokens = [verb]
                if task_dict["particle"]:
                    tokens.append(task_dict["particle"])
                if task_dict["direct_object_modifiers"]:
                    tokens += task_dict["direct_object_modifiers"]
                if task_dict["direct_object"]:
                    tokens.append(task_dict["direct_object"])
                if task_dict["preposition"]:
                    tokens.append(task_dict["preposition"])
                if task_dict["preposition_object_modifiers"]:
                    tokens += task_dict["preposition_object_modifiers"]
                if task_dict["preposition_object"]:
                    tokens.append(task_dict["preposition_object"])
                task = " ".join(tokens)
                yield task

    def lemmatize_dicts(self, task_dicts):
        for i, task_dict in enumerate(task_dicts):
            if "verb" in task_dict:
                lemma = getLemma(task_dict["verb"], "VERB")
                task_dict["verb"] = lemma[0]
        #             if "direct_object" in task_dict:
        #                 lemma = getLemma(task_dict["direct_object"], "NOUN", False)
        #                 if lemma: task_dict["direct_object"] = lemma[0]
        #             if "preposition_object" in task_dict:
        #                 lemma = getLemma(task_dict["preposition_object"], "NOUN", False)
        #                 if lemma: task_dict["preposition_object"] = lemma[0]
        return task_dicts


class semantic_role_labeling(object):
    def execute(self, description: str, original_des: str) -> dict:
        '''
        Semantic Role Labeling
        :return:
        '''
        srl_info = predictor.predict(sentence=description)
        srl_result = self.arrange_srl_info(srl_info, original_des)
        return srl_result

    def arrange_srl_info(self, srl_info: dict, description: str) -> dict:
        if srl_info["verbs"] == []:
            return {}
        words, verb_tags = srl_info["words"], srl_info["verbs"]
        # parse srl info
        parsed_info = self.get_ARG_ARGM(verb_tags, words, 0, 5)  # get the first verb

        # if srl info existed
        if parsed_info:
            arranged_info = {}
            parsed_info["verb"] = verb_tags[0]['verb']
            semantic_label, functionality_description, argm_label = self.get_verb_arg_argm(parsed_info)
            arranged_info["description"] = description
            arranged_info["semantic_label"] = semantic_label
            arranged_info["functionality_description"] = functionality_description
            arranged_info["argm_label"] = argm_label
            return arranged_info
        else:
            return {}

    def get_ARG_ARGM(self, verb_tags, words, verb_pos, arg_number) -> dict:
        '''
        get arg and argm
        :param verb_tags: the label after srl
        :param words: the list after split token
        :param verb_pos: the position of verb
        :param arg_number: the max number of arg or argm
        :return: info
        '''
        other_tag_list = ["ARGM-ADV", "ARGM-BNF", "ARGM-CND", "ARGM-DIR", "ARGM-DIS", "ARGM-DGR",
                          "ARGM-EXT", "ARGM-GOL",
                          "ARGM-FRQ", "ARGM-LOC", "ARGM-MNR", "ARGM-PRP", "ARGM-TMP", "ARGM-TPC", "ARGM-PRD"]
        tags = verb_tags[verb_pos]['tags']
        info = {}
        for _ in range(arg_number):
            B_flag = "B-ARG" + str(_)
            I_flag = "I-ARG" + str(_)

            # find ARG
            for item in tags:
                if item[:5] == "B-ARG" and item[:6] != "B-ARGM":
                    B_flag, I_flag = item, "I-ARG" + str(item[-1])
                    start = tags.index(B_flag)
                    end = max([i for i, x in enumerate(tags) if x == I_flag] + [start]) + 1
                    arg_temp = words[start:end]
                    info['ARG' + str(item[-1])] = " ".join(arg_temp)

            # find ARGM
            for item in other_tag_list:
                B_ARGM_falg = "B-" + str(item)
                I_ARGM_flag = "I-" + str(item)
                if B_ARGM_falg in tags:
                    start = tags.index(B_ARGM_falg)
                    end = max([i for i, x in enumerate(tags) if x == I_ARGM_flag] + [start]) + 1
                    ARGM_temp = words[start:end]
                    info[item] = " ".join(ARGM_temp)
        return info

    def get_verb_arg_argm(self, labeled_data: dict):
        '''
        get data as follow:
            "semantic_label":[...]
            "argm_label":[...]
            "verb_arg_dec":....
        :param parsed_info:
        :return:
        '''
        label_tag = list(labeled_data.keys())
        semantic_label = {"verb": None, "ARG1": None, "ARG2": None, "ARG3": None, "ARG4": None}
        argm_label = {}
        for tag in label_tag:
            # verb
            if tag == 'verb':
                semantic_label[tag] = labeled_data[tag]
            # argm
            elif tag[:4] == 'ARGM':
                argm_label[tag] = labeled_data[tag]
            # arg1-4
            elif tag[:3] == 'ARG' and tag[3] in ["1", "2", "3", "4"]:
                semantic_label[tag] = labeled_data[tag]
        functionality_description = " ".join([semantic_label[item] for item in semantic_label if semantic_label[item]])
        return semantic_label, functionality_description, argm_label


class syntax_role_labeling(object):
    def execute(self, srl_result: dict, description) -> dict:
        if srl_result == {}:
            srl_result["description"] = description
            srl_result["semantic_label"] = {}
            srl_result["argm_label"] = {}
            srl_result["functionality_description"] = description

        parse_desc = parse_functionality_description()
        use_string = [srl_result["functionality_description"]]
        task_list = []
        syntax_label = None
        for tasks in parse_desc.extract_task_dicts(use_string):
            syntax_label = tasks[0]
            for task in parse_desc.parse_task_dicts(tasks):
                task_list.append(task)
        if task_list and syntax_label:
            srl_result["syntax_label"] = syntax_label[0]
            # lemman syntax_label verb
            lemma = getLemma(srl_result["syntax_label"]["verb"], "VERB")[0]
            verb = getInflection(lemma, "VB")[0]
            srl_result["syntax_label"]["verb"] = verb

            # add event
            info = srl_result["syntax_label"]
            if info["direct_object"] != '' and info["preposition_object"] == '':
                event_name = " ".join([info["verb"], info["direct_object"]])
            elif info["preposition_object"] != '' and info["direct_object"] == '':
                event_name = " ".join([info["verb"], info["preposition"], info["preposition_object"]])
            elif info["direct_object"] != '' and info["preposition_object"] != '':
                event_name = " ".join(
                    [info["verb"], info["direct_object"], info["preposition"], info["preposition_object"]])
            srl_result["event"] = event_name
        else:
            return {}
        return srl_result


class Information_Extraction(object):
    def preprocess_description(self, description: str) -> str:
        '''
        preprocess description:
            1. remove bracket
            2. add "this method" if the tag of first word is "VBZ"
        :param description:
        :return:
        '''
        description = description.lower()

        # process 1: remove bracket
        for match in re.finditer(r"\W\(.+?\)\W", description):
            matched = match[0].strip()
            description = description.replace(matched, "", 1)
        description = description.strip()

        # process 2: add "this method"
        # first_word = description.split()[0]
        # first_word_lemmas = getLemma(first_word, "VERB", lemmatize_oov=False)
        # for item in first_word_lemmas:
        #     vbz = getInflection(item, tag='VBZ')
        #     if first_word in vbz:
        #         description = " ".join(["this method", description])
        # description = " ".join(description.split())

        # process 3:

        return description

    def execute(self, description: str) -> dict:
        original_des = description

        # step1: preprocess_description
        description = self.preprocess_description(description)

        # step2: semantic role labeling
        srl_result = semantic_role_labeling().execute(description, original_des)

        # step3: syntax role labeling
        srl_result = syntax_role_labeling().execute(srl_result, description)

        return srl_result

    def execute_no_semantic_role_label(self, description: str) -> dict:
        original_des = description

        # step1: preprocess_description
        description = self.preprocess_description(description)

        srl_result = {"functionality_description": description}

        # step2: syntax role labeling
        srl_result = syntax_role_labeling().execute(srl_result, description)

        return srl_result

    def extract_all_information(self):
        data = pd.read_csv(crawl_data_DIR + "original_data.csv")
        descriptions = list(data.functionality_description)
        descriptions = list(set(descriptions))

        all_srl_result = []
        for _, description in enumerate(tqdm(descriptions)):
            original_des = description
            description = self.preprocess_description(description)
            srl_result = semantic_role_labeling().execute(description, original_des)
            all_srl_result.append(srl_result)
        dump_dict_to_json_file(build_kg_data_DIR + "srl_cache.json", all_srl_result)

        info = []
        for _, item in enumerate(tqdm(all_srl_result)):
            result = syntax_role_labeling().execute(item, all_srl_result[_]["description"])
            if result:
                info.append(result)
        dump_dict_to_json_file(build_kg_data_DIR + "after_semantic_syntax_label_info.json", info)

    def do_it(self):
        data = pd.read_csv(crawl_data_DIR + "original_data.csv")
        descriptions = list(data.functionality_description)
        descriptions = list(set(descriptions))

        srl_cache = get_data_from_json(build_kg_data_DIR + "srl_cache.json")

        assert len(descriptions) == len(srl_cache)

        srl_index = {}
        for _, item in enumerate(srl_cache):
            if item != {}:
                srl_index[item["description"]] = _
        srl_index_key = list(srl_index.keys())

        info = []
        for _, description in enumerate(tqdm(descriptions)):
            description = self.preprocess_description(description)
            if description in srl_index_key:
                srl_result = srl_cache[srl_index[description]]
            else:
                srl_result = {}
            result = syntax_role_labeling().execute(srl_result, description)
            if result:
                info.append(result)

        dump_dict_to_json_file(build_kg_data_DIR + "after_semantic_syntax_label_info.json", info)


if __name__ == '__main__':
    description = "prints a stack trace of the current thread to the standard error stream."
    # Information_Extraction().execute(description)
    # Information_Extraction().extract_all_information()
    # Information_Extraction().execute(description)
    Information_Extraction().do_it()
