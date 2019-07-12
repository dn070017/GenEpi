# -*- coding: utf-8 -*-
"""
Created on Feb 2018

@author: Chester (Yu-Chuan Chang)
"""

""""""""""""""""""""""""""""""
# import libraries
""""""""""""""""""""""""""""""
import os
import sys
import itertools
import numpy as np
np.seterr(divide='ignore', invalid='ignore')
from sklearn.feature_selection import VarianceThreshold
from sklearn.feature_selection import f_regression
from scipy.sparse import coo_matrix
from sklearn.utils import shuffle
from sklearn import linear_model
from sklearn.model_selection import KFold
from sklearn.model_selection import GridSearchCV
import scipy.stats as stats

from genepi.tools import randomized_l1

import warnings
warnings.filterwarnings('ignore')
# ignore all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

""""""""""""""""""""""""""""""
# define functions 
""""""""""""""""""""""""""""""
def RandomizedLassoRegression(np_X, np_y):
    X = np_X
    y = np_y
    X_sparse = coo_matrix(X)
    X, X_sparse, y = shuffle(X, X_sparse, y, random_state=0)
    estimator = randomized_l1.RandomizedLasso(n_jobs=1, n_resampling=100)
    estimator.fit(X, y)
    
    return estimator.scores_

def LassoRegressionCV(np_X, np_y, int_kOfKFold = 2, int_nJobs = 4):
    X = np_X
    y = np_y
    X_sparse = coo_matrix(X)
    X, X_sparse, y = shuffle(X, X_sparse, y, random_state=0)
    kf = KFold(n_splits=int_kOfKFold)
    
    list_target = []
    list_predict = []
    list_weight = []
    for idxTr, idxTe in kf.split(X):
        alpha = np.logspace(-10, 10, 200)
        parameters = [{'alpha':alpha}]
        kf_estimator = KFold(n_splits=2)
        estimator_lasso = linear_model.Lasso()
        estimator_grid = GridSearchCV(estimator_lasso, parameters, scoring='neg_mean_squared_error', n_jobs=int_nJobs, cv=kf_estimator)
        estimator_grid.fit(X[idxTr], y[idxTr])
        list_label = estimator_grid.best_estimator_.predict(X[idxTe])
        list_weight.append([float(item) for item in estimator_grid.best_estimator_.coef_])
        for idx_y, idx_label in zip(list(y[idxTe]), list_label):
            list_target.append(float(idx_y))
            list_predict.append(idx_label)
    np_weight = np.array(list_weight)
    np_weight = np.average(list_weight, axis=0)
    float_pearson = stats.stats.pearsonr(list_target, list_predict)[0]
    float_spearman = stats.stats.spearmanr(list_target, list_predict)[0]
    
    return (float_pearson + float_spearman) / 2, np_weight

def FeatureEncoderLasso(np_genotype_rsid, np_genotype, np_phenotype, int_dim):
    ### combinatorial encoding
    np_interaction = np_genotype
    list_interaction_rsid = list(np_genotype_rsid)    

    list_combs = list(itertools.combinations(range(int(np_interaction.shape[1]/int_dim)), 2))
    
    for idx_combs in range(len(list_combs)):
        try:
            ### generate interaction terms
            tuple_comb = list_combs[idx_combs]
            np_this_interaction = np.zeros([np_phenotype.shape[0], int_dim**2], dtype='int8')
            list_this_interaction_id = []
            for idx_x in range(int_dim):
                for idx_y in range(int_dim):
                    np_this_interaction_term = (np_genotype[:, tuple_comb[0] * int_dim + idx_x] * np_genotype[:, tuple_comb[1] * int_dim + idx_y]).astype(np.int8)
                    if not(np.array_equal(np_this_interaction_term, np_genotype[:, tuple_comb[0] * int_dim + idx_x])) and not(np.array_equal(np_this_interaction_term, np_genotype[:, tuple_comb[1] * int_dim + idx_y])):
                        np_this_interaction[:, idx_x * int_dim + idx_y] = np_this_interaction_term
                    list_this_interaction_id.append(np_genotype_rsid[tuple_comb[0] * int_dim + idx_x] + "*" + np_genotype_rsid[tuple_comb[1] * int_dim + idx_y])
            
            ### variance check (detect variance < 0.05)
            sk_variance = VarianceThreshold(threshold=(.95 * (1 - .95)))
            np_this_interaction = sk_variance.fit_transform(np_this_interaction)
            np_this_interaction_id = np.array(list_this_interaction_id)
            np_this_interaction_id = np.array(np_this_interaction_id[sk_variance.get_support()])
            
            ### f regression feature selection
            np_fRegression = -np.log10(f_regression(np_this_interaction.astype(int), np_phenotype[:, -1].astype(float))[1])
            np_selectedIdx = np.array([x > 2 for x in np_fRegression])
            np_this_interaction = np_this_interaction[:, np_selectedIdx]
            np_this_interaction_id = np_this_interaction_id[np_selectedIdx]
        
            ### append insteraction terms
            int_num_interaction = np_this_interaction.shape[1]
            if int_num_interaction == 0:
                continue
            np_interaction_append = np.empty((np_interaction.shape[0], np_interaction.shape[1] + int_num_interaction), dtype='int')
            np_interaction_append[:,:-(int_num_interaction)] = np_interaction
            np_interaction_append[:,-(int_num_interaction):] = np_this_interaction
            np_interaction = np_interaction_append
            list_interaction_rsid.extend(list(np_this_interaction_id))
        except:
            pass

    return np.array(list_interaction_rsid), np_interaction

def FilterInLoading(np_genotype, np_phenotype):
    try:
        ### variance check (detect variance < 0.05)
        sk_variance = VarianceThreshold(threshold=(.95 * (1 - .95)))
        np_genotype = sk_variance.fit_transform(np_genotype)
        
        ### f regression feature selection
        np_fRegression = -np.log10(f_regression(np_genotype.astype(int), np_phenotype[:, -1].astype(float))[1])
        np_selectedIdx = np.array([x > 2 for x in np_fRegression])
        np_genotype = np_genotype[:, np_selectedIdx]
        
        return np_genotype.shape[1]
    
    except:
        return 0

""""""""""""""""""""""""""""""
# main function
""""""""""""""""""""""""""""""
def SingleGeneEpistasisLasso(str_inputFileName_genotype, str_inputFileName_phenotype, str_outputFilePath = "", int_kOfKFold = 2, int_nJobs = 4):    
    ### set path of output file
    if str_outputFilePath == "":
        str_outputFilePath = os.path.dirname(str_inputFileName_genotype)
    
    #-------------------------
    # load data
    #-------------------------
    ### count lines of input files
    int_num_phenotype = sum(1 for line in open(str_inputFileName_phenotype))
    
    ### get phenotype file
    list_phenotype = []
    with open(str_inputFileName_phenotype, 'r') as file_inputFile:
        for line in file_inputFile:
            list_phenotype.append(line.strip().split(","))
    np_phenotype = np.array(list_phenotype, dtype=np.float)
    del list_phenotype
    
    ### get genotype file
    list_genotype = [[] for x in range(int_num_phenotype)]
    list_genotype_rsid = []
    with open(str_inputFileName_genotype, 'r') as file_inputFile:
        for line in file_inputFile:
            list_thisSnp = line.strip().split(" ")
            np_this_genotype = np.empty([int_num_phenotype, 3], dtype='int8')
            for idx_subject in range(0, int_num_phenotype):
                list_allelType = [0, 0, 0]
                list_allelType[np.argmax(list_thisSnp[idx_subject * 3 + 5 : idx_subject * 3 + 8])] = 1
                np_this_genotype[idx_subject, :] = list_allelType
            if FilterInLoading(np_this_genotype, np_phenotype) == 0:
                continue
            for idx_subject in range(0, int_num_phenotype):
                list_allelType = [0, 0, 0]
                list_allelType[np.argmax(list_thisSnp[idx_subject * 3 + 5 : idx_subject * 3 + 8])] = 1
                list_genotype[idx_subject].extend(list_allelType)
            list_genotype_rsid.append(list_thisSnp[1] + "_AA")
            list_genotype_rsid.append(list_thisSnp[1] + "_AB")
            list_genotype_rsid.append(list_thisSnp[1] + "_BB")
    np_genotype = np.array(list_genotype, dtype=np.int8)
    np_genotype_rsid = np.array(list_genotype_rsid)
    
    if np_genotype_rsid.shape[0] == 0:
        return 0.0
    
    #-------------------------
    # preprocess data
    #-------------------------    
    ### generate interaction terms
    np_genotype_rsid, np_genotype = FeatureEncoderLasso(np_genotype_rsid, np_genotype, np_phenotype, 3)
    
    #-------------------------
    # select feature
    #-------------------------    
    ### random lasso feature selection
    np_randWeight = np.array(RandomizedLassoRegression(np_genotype, np_phenotype[:, -1].astype(float)))
    np_selectedIdx = np.array([x >= 0.1 for x in np_randWeight])
    np_randWeight = np_randWeight[np_selectedIdx]
    np_genotype = np_genotype[:, np_selectedIdx]
    np_genotype_rsid = np_genotype_rsid[np_selectedIdx]
    if np_genotype_rsid.shape[0] == 0:
        return 0.0
    
    #-------------------------
    # build model
    #-------------------------
    float_AVG_S_P, np_weight = LassoRegressionCV(np_genotype, np_phenotype[:, -1].astype(float), int_kOfKFold, int_nJobs)
    if float_AVG_S_P == 0.0:
        return 0.0
    
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
    ### calculate student t-test p-value
    np_fRegression = -np.log10(f_regression(np_genotype.astype(int), np_phenotype[:, -1].astype(float))[1])
        
    ### calculate genotype frequency
    np_genotypeFreq = np.sum(np_genotype, axis=0).astype(float) / np_genotype.shape[0]
    
    #-------------------------
    # output results
    #-------------------------
    ### output statistics of features
    with open(os.path.join(str_outputFilePath, os.path.basename(str_inputFileName_genotype).split("_")[0] + "_Result.csv"), "w") as file_outputFile:
        file_outputFile.writelines("rsID,weight,student-t-test_log_p-value,genotype_frequency" + "\n")
        for idx_feature in range(0, np_genotype_rsid.shape[0]):
            file_outputFile.writelines(str(np_genotype_rsid[idx_feature,]) + "," + str(np_weight[idx_feature,]) + "," + str(np_fRegression[idx_feature,]) + "," + str(np_genotypeFreq[idx_feature]) + "\n")
    
    ### output feature
    with open(os.path.join(str_outputFilePath, os.path.basename(str_inputFileName_genotype).split("_")[0] + "_Feature.csv"), "w") as file_outputFile:
        file_outputFile.writelines(",".join(np_genotype_rsid) + "\n")
        for idx_subject in range(0, np_genotype.shape[0]):
            file_outputFile.writelines(",".join(np_genotype[idx_subject, :].astype(str)) + "\n")
    
    return float_AVG_S_P

def BatchSingleGeneEpistasisLasso(str_inputFilePath_genotype, str_inputFileName_phenotype, str_outputFilePath = "", int_kOfKFold = 2, int_nJobs = 4):
    ### set default output path
    if str_outputFilePath == "":
        str_outputFilePath = os.path.abspath(os.path.join(str_inputFilePath_genotype, os.pardir)) + "/singleGeneResult/"
    ### if output folder doesn't exist then create it
    if not os.path.exists(str_outputFilePath):
        os.makedirs(str_outputFilePath)
    
    ### scan all of the gen file in path
    list_genotypeFileName = []
    for str_fileName in os.listdir(str_inputFilePath_genotype):
        if ".gen" in str_fileName:
            list_genotypeFileName.append(str_fileName)
    
    ### batch PolyLogisticRegression
    int_count_gene = 0
    with open(str_outputFilePath + "All_Lasso_k" + str(int_kOfKFold) + ".csv", "w") as file_outputFile:
        file_outputFile.writelines("GeneSymbol,AVG_S_P" + "\n")
        for item in list_genotypeFileName:
            int_count_gene = int_count_gene + 1
            str_genotypeFileName = os.path.join(str_inputFilePath_genotype, item)
            float_AVG_S_P = SingleGeneEpistasisLasso(str_genotypeFileName, str_inputFileName_phenotype, str_outputFilePath, int_kOfKFold, int_nJobs)
            file_outputFile.writelines(item.split("_")[0] + "," + str(float_AVG_S_P) + "\n")
            str_print = "step4: Processing: " + "{0:.2f}".format(float(int_count_gene) / len(list_genotypeFileName) * 100) + "% - " + item + ": " + str(float_AVG_S_P) + "\t\t"
            sys.stdout.write('%s\r' % str_print)
            sys.stdout.flush()
    
    print("step4: Detect single gene epistasis. DONE! \t\t\t\t")