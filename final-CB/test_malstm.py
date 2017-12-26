import os 
import sys
import csv
import time
import config
import pickle
import logging
import itertools
import numpy as np
import pandas as pd 
from termcolor import colored,cprint

import gensim
from gensim.models import Word2Vec

import jieba

from scipy import spatial

import keras
from keras.optimizers import SGD, Adam, Adagrad, RMSprop
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.models import Sequential,  load_model, Model
from keras.layers import Activation, Flatten, Dropout, Dense, Embedding, LSTM, GRU, Merge, Input 
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.optimizers import Adadelta

import keras.backend as K
from sklearn.model_selection import train_test_split

def cut(s):
    return list(jieba.cut(s))

def process(s):
  rtns = s.split('\t')
  rtns = [cut(rtn[rtn.find(':')+1 : ]) for rtn in rtns]
  return rtns

jieba.set_dictionary(config.jieba_dict_path)
word_embedding_model = Word2Vec.load(config.word_embedding_model_path)

with open(config.sentences_pickle_path,'rb') as handle:
    sentences = pickle.load(handle)

max_length = config.max_length

jieba_tokenizer_dict = {}

sen = sentences 
idx = 1 
for i in range(len(sen)):
    for j in range(len(sen[i])):
        if sen[i][j] not in jieba_tokenizer_dict :
            jieba_tokenizer_dict[sen[i][j]] = idx
            idx += 1

test_num = 5

compare = []
with open('data/self_ans.csv','r') as f:
    csvf = csv.reader(f)
    next(csvf)
    for row in itertools.islice(csvf, test_num):
    # for row in csvf:
        compare.append(row[1])
f.close()


tmp_Us = []
tmp_Rs = []
total_test_case = 5060
with open('data/testing_data.csv', 'r') as f:
  csvf = csv.reader(f)
  next(csvf)
  predict = [] 
  for row in itertools.islice(csvf, test_num):
#   for row in csvf:
    choice_similiar = []

    U = process(row[1].replace(" ",""))
    Us = []
    for i in range(len(U)):
        Us += U[i]
    print(Us)
    tmp_Us.append(Us)

    Rs = process(row[2].replace(" ",""))
    print(Rs)
    tmp_Rs.append(Rs)

f.close()

x_test_q = []
x_test_a = []

for i in range(test_num):
    tmp = []
    for j in range(len(tmp_Us[i])):
        if tmp_Us[i][j] in jieba_tokenizer_dict :
            tmp.append(jieba_tokenizer_dict[tmp_Us[i][j]])
        else:
            tmp.append(0)
    for k in range(config.option_num):
        x_test_q.append(tmp)
        tmp_a = []
        for j in range(len(tmp_Rs[i][k])):
            if tmp_Rs[i][k][j] in jieba_tokenizer_dict :
                tmp_a.append(jieba_tokenizer_dict[tmp_Rs[i][k][j]])
            else:
                tmp_a.append(0)
        x_test_a.append(tmp_a)


x_test_q = pad_sequences(x_test_q,maxlen=max_length,padding='post')
x_test_a = pad_sequences(x_test_a,maxlen=max_length,padding='post')
x_test_q = np.array(x_test_q)
x_test_a = np.array(x_test_a)

embedding_matrix = np.zeros((53597, 500))
for key, value in jieba_tokenizer_dict.items(): # key = chinese value = idx
    if key in word_embedding_model:
        embedding_vector = word_embedding_model[key]
        if embedding_vector is not None:
            embedding_matrix[value] = embedding_vector


for i in range(len(x_test_a)):
    print(x_test_q[i])
    print(x_test_a[i])



n_hidden = 64
gradient_clipping_norm = 1.25
batch_size = 64
n_epoch = 50

def exponent_neg_manhattan_distance(left, right):
    return K.exp(-K.sum(K.abs(left-right), axis=1, keepdims=True))

# The visible layer
left_input = Input(shape=(max_length,), dtype='int32')
right_input = Input(shape=(max_length,), dtype='int32')

embedding_layer = Embedding(53597,500, weights=[embedding_matrix], input_length=max_length, trainable=False)

# Embedded version of the inputs
encoded_left = embedding_layer(left_input)
encoded_right = embedding_layer(right_input)

# Since this is a siamese network, both sides share the same LSTM
shared_lstm = LSTM(n_hidden)

left_output = shared_lstm(encoded_left)
right_output = shared_lstm(encoded_right)

# Calculates the distance as defined by the MaLSTM model
malstm_distance = Merge(mode=lambda x: exponent_neg_manhattan_distance(x[0], x[1]), output_shape=lambda x: (x[0][0], 1))([left_output, right_output])

# Pack it all up into a model
malstm = Model([left_input, right_input], [malstm_distance])

# Adadelta optimizer, with gradient clipping by norm
optimizer = Adadelta(clipnorm=gradient_clipping_norm)

malstm.compile(loss='mean_squared_error', optimizer=optimizer, metrics=['accuracy'])



malstm.load_weights('model/current_malstm_weights.h5')
preds = malstm.predict([x_test_q,x_test_a])
print(preds)


ans = []

for i in range(test_num):
    option = []
    for j in range(6):
        option.append(preds[i*6+j])
    ans.append(np.argmax(option))

print(ans)
        


for i in range(test_num):
    if int(compare[i]) == predict[i]:
        ct += 1

print(colored("{}/{}={}%".format(ct,test_num,ct/test_num),'red'))
