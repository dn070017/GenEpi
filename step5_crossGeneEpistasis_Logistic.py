# -*- coding: utf-8 -*-
"""
Created on Feb 2018

@author: Chester (Yu-Chuan Chang)
"""

""""""""""""""""""""""""""""""
# import libraries
""""""""""""""""""""""""""""""
import os
import numpy as np
np.seterr(divide='ignore', invalid='ignore')
from sklearn.feature_selection import chi2
from sklearn import linear_model
from sklearn.model_selection import KFold
from sklearn.model_selection import GridSearchCV
import sklearn.metrics as skMetric
import scipy.stats as stats

from genepi.step4_singleGeneEpistasis_Logistic import RandomizedLogisticRegression
from genepi.step4_singleGeneEpistasis_Logistic import LogisticRegressionL1CV
from genepi.step4_singleGeneEpistasis_Logistic import FeatureEncoderLogistic

import warnings
warnings.filterwarnings('ignore')
# ignore all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

""""""""""""""""""""""""""""""
# define functions 
""""""""""""""""""""""""""""""
def LogisticRegressionL1(np_X, np_y, int_nJobs = 4):
    X = np_X
    y = np_y
    
    list_target = []
    list_predict = []
    
    cost = [2**x for x in range(-8, 8)]
    parameters = [{'C':cost, 'penalty':['l1'], 'dual':[False], 'class_weight':['balanced']}]
    kf_estimator = KFold(n_splits=2)
    estimator_logistic = linear_model.LogisticRegression()
    estimator_grid = GridSearchCV(estimator_logistic, parameters, scoring='f1', n_jobs=int_nJobs, cv=kf_estimator)
    estimator_grid.fit(X, y)
    list_label = estimator_grid.best_estimator_.predict(X)
    for idx_y, idx_label in zip(list(y), list_label):
        list_target.append(float(idx_y))
        list_predict.append(idx_label)
    float_f1Score = skMetric.f1_score(list_target, list_predict)
    
    return float_f1Score

def GenerateContingencyTable(np_genotype, np_phenotype):
    np_contingency = np.array([[0, 0], [0, 0]])
    for idx_subject in range(0, np_genotype.shape[0]):
        np_contingency[int(np_genotype[idx_subject]), int(np_phenotype[idx_subject])] = np_contingency[int(np_genotype[idx_subject]), int(np_phenotype[idx_subject])] + 1
    np_contingency = np.rot90(np_contingency)
    np_contingency = np.rot90(np_contingency)
    
    return np_contingency

""""""""""""""""""""""""""""""
# main function
""""""""""""""""""""""""""""""
def CrossGeneEpistasisLogistic(str_inputFilePath_feature, str_inputFileName_phenotype, str_inputFileName_score = "", str_outputFilePath = "", int_kOfKFold = 2, int_nJobs = 4):   
    ### set default output path
    if str_outputFilePath == "":
        str_outputFilePath = os.path.abspath(os.path.join(str_inputFilePath_feature, os.pardir)) + "/crossGeneResult/"
    ### if output folder doesn't exist then create it
    if not os.path.exists(str_outputFilePath):
        os.makedirs(str_outputFilePath)
    
    ### set default score file name
    if str_inputFileName_score == "":
        for str_fileName in os.listdir(str_inputFilePath_feature):
            if str_fileName.startswith("All_Logistic"):
                str_inputFileName_score = os.path.join(str_inputFilePath_feature, str_fileName)

    #-------------------------
    # load data
    #-------------------------
    ### scan score file and exclude useless genes
    dict_score = {}
    with open(str_inputFileName_score, "r") as file_inputFile:
        file_inputFile.readline()
        for line in file_inputFile:
            list_thisScore = line.strip().split(",")
            if list_thisScore[1] == "MemErr" or float(list_thisScore[1]) == 0.0:
                pass
            else:
                dict_score[list_thisScore[0]] = float(list_thisScore[1])
    
    ### get all the file names of feature file
    list_featureFileName = []
    for str_fileName in os.listdir(str_inputFilePath_feature):
        if "Feature.csv" in str_fileName:
            list_featureFileName.append(str_fileName)
    
    ### get all selected snp ids
    list_genotype_rsid = []
    for item in list_featureFileName:
        with open(os.path.join(str_inputFilePath_feature, item), "r") as file_inputFile:
            ### grep the header
            list_rsids = file_inputFile.readline().strip().split(",")
            for rsid in list_rsids:
                list_genotype_rsid.append(rsid)
    np_genotype_rsid = np.array(list_genotype_rsid)
    
    ### count lines of input files
    int_num_genotype = len(np_genotype_rsid)
    int_num_phenotype = sum(1 for line in open(str_inputFileName_phenotype))
    
    ### get phenotype file
    list_phenotype = []
    with open(str_inputFileName_phenotype, 'r') as file_inputFile:
        for line in file_inputFile:
            list_phenotype.append(line.strip().split(","))
    np_phenotype = np.array(list_phenotype, dtype=np.float)
    del list_phenotype
    
    ### get genotype file
    ### declare a dictionary for mapping snp and gene
    dict_geneMap ={}
    idx_genotype_rsid = 0
    np_genotype = np.empty([int_num_phenotype, int_num_genotype], dtype='int8')
    for item in list_featureFileName:
        with open(os.path.join(str_inputFilePath_feature, item), "r") as file_inputFile:
            ### grep feature from header of feature file
            list_rsids = file_inputFile.readline().strip().split(",")
            for rsid in list_rsids:
                ### key: rsIDs of a feature; value: gene symbol
                dict_geneMap[rsid] = item.split("_")[0]
            idx_phenotype = 0
            ### read feaure and write into np_genotype
            for line in file_inputFile:
                np_genotype[idx_phenotype, idx_genotype_rsid:idx_genotype_rsid + len(list_rsids)] = np.array([float(x) for x in line.strip().split(",")], dtype='int')
                idx_phenotype = idx_phenotype + 1
            idx_genotype_rsid = idx_genotype_rsid + len(list_rsids)
    
    #-------------------------
    # preprocess data
    #-------------------------
    ### select degree 1 feature
    np_genotype_rsid_degree = np.array([str(x).count('*') + 1 for x in np_genotype_rsid])
    np_selectedIdx = np.array([x == 1 for x in np_genotype_rsid_degree])
    np_genotype_degree1 = np_genotype[:, np_selectedIdx]
    np_genotype_degree1_rsid = np_genotype_rsid[np_selectedIdx]
    
    ### remove redundant polynomial features
    np_genotype_degree1, np_selectedIdx = np.unique(np_genotype_degree1, axis=1, return_index=True)
    np_genotype_degree1_rsid = np_genotype_degree1_rsid[np_selectedIdx]
    
    ### generate cross gene interations
    np_genotype_crossGene_rsid, np_genotype_crossGene = FeatureEncoderLogistic(np_genotype_degree1_rsid, np_genotype_degree1, np_phenotype, 1)
    
    ### remove degree 1 feature from dataset
    np_selectedIdx = np.array([x != 1 for x in np_genotype_rsid_degree])
    np_genotype = np_genotype[:, np_selectedIdx]
    np_genotype_rsid = np_genotype_rsid[np_selectedIdx]
    
    ### concatenate cross gene interations
    if np_genotype_degree1.shape[1] > 0:
        np_genotype = np.concatenate((np_genotype, np_genotype_crossGene), axis=1)
        np_genotype_rsid = np.concatenate((np_genotype_rsid, np_genotype_crossGene_rsid))
    
    #-------------------------
    # select feature
    #-------------------------    
    ### random logistic feature selection
    np_randWeight = np.array(RandomizedLogisticRegression(np_genotype, np_phenotype[:, -1].astype(int)))    
    np_selectedIdx = np.array([x >= 0.25 for x in np_randWeight])
    np_randWeight = np_randWeight[np_selectedIdx]
    np_genotype = np_genotype[:, np_selectedIdx]
    np_genotype_rsid = np_genotype_rsid[np_selectedIdx]
    if np_genotype_rsid.shape[0] == 0:
        return 0.0
    
    #-------------------------
    # build model
    #-------------------------
    float_f1Score_test, np_weight = LogisticRegressionL1CV(np_genotype, np_phenotype[:, -1].astype(int), int_kOfKFold, int_nJobs)
    float_f1Score_train = LogisticRegressionL1(np_genotype, np_phenotype[:, -1].astype(int), int_nJobs)
    
    ### filter out zero-weight features
    np_selectedIdx = np.array([x != 0.0 for x in np_weight])
    np_weight = np_weight[np_selectedIdx]
    np_genotype = np_genotype[:, np_selectedIdx]
    np_genotype_rsid = np_genotype_rsid[np_selectedIdx]
    if np_genotype_rsid.shape[0] == 0:
        return 0.0
    
    #-------------------------
    # analyze result
    #-------------------------
    ### calculate chi-square p-value
    np_chi2 = -np.log10(chi2(np_genotype.astype(int), np_phenotype[:, -1].astype(int))[1])
    list_oddsRatio = []
    for idx_feature in range(0, np_genotype.shape[1]):
        np_contingency = GenerateContingencyTable(np_genotype[:, idx_feature], np_phenotype[:, -1])
        oddsratio, pvalue = stats.fisher_exact(np_contingency)
        list_oddsRatio.append(oddsratio)
        
    ### calculate genotype frequency
    np_genotypeFreq = np.sum(np_genotype, axis=0).astype(float) / np_genotype.shape[0]
    
    #-------------------------
    # output results
    #-------------------------
    ### output statistics of features
    with open(os.path.join(str_outputFilePath, "Result.csv"), "w") as file_outputFile:
        file_outputFile.writelines("rsid,weight,chi-square_log_p-value,odds_ratio,genotype_frequency,geneSymbol,singleGeneScore" + "\n")
        for idx_feature in range(0, np_genotype_rsid.shape[0]):
            ### if this feature is single gene epistasis
            if np_genotype_rsid[idx_feature,] in dict_geneMap.keys():
                str_thisOutput = str(np_genotype_rsid[idx_feature,]) + "," + str(np_weight[idx_feature,]) + "," + str(np_chi2[idx_feature,]) + "," + str(list_oddsRatio[idx_feature]) + "," + str(np_genotypeFreq[idx_feature]) + "," + str(dict_geneMap[np_genotype_rsid[idx_feature,]]) + "," + str(dict_score[dict_geneMap[np_genotype_rsid[idx_feature,]]]) + "\n"
                file_outputFile.writelines(str_thisOutput)
            ### else this feature is cross gene epistasis
            else:
                str_thisOutput = str(np_genotype_rsid[idx_feature,]) + "," + str(np_weight[idx_feature,]) + "," + str(np_chi2[idx_feature,]) + "," + str(list_oddsRatio[idx_feature]) + "," + str(np_genotypeFreq[idx_feature]) + "," + str(dict_geneMap[np_genotype_rsid[idx_feature,].split("*")[0]]) + "*" + str(dict_geneMap[np_genotype_rsid[idx_feature,].split("*")[1]]) + ", " + "\n"
                file_outputFile.writelines(str_thisOutput)
            
    ### output feature
    with open(os.path.join(str_outputFilePath, "Feature.csv"), "w") as file_outputFile:
        file_outputFile.writelines(",".join(np_genotype_rsid) + "\n")
        for idx_subject in range(0, np_genotype.shape[0]):
            file_outputFile.writelines(",".join(np_genotype[idx_subject, :].astype(str)) + "\n")

    print("step5: Detect cross gene epistasis. DONE! (Training score:" + "{0:.2f}".format(float_f1Score_train) + "; " + str(int_kOfKFold) + "-fold Test Score:" + "{0:.2f}".format(float_f1Score_test) + ")")
    
    return float_f1Score_train, float_f1Score_test