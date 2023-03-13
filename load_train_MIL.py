# -*- coding: utf-8 -*-
"""
Created on Thu Nov 17 11:52:02 2022

@author: AmayaGS
"""

import os, os.path
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
import sys

from PIL import Image
from PIL import ImageFile

import pandas as pd

from matplotlib import pyplot as plt

import torch
import torch.nn as nn

import torch.optim as optim

from torchvision import transforms

from loaders import Loaders

from training_loops import train_att_slides, train_att_multi_slide, test_slides, soft_vote
from graph_train_loop import train_graph_slides, train_graph_multi_stain

from clam_model import VGG_embedding, GatedAttention
from Graph_model import GAT_topK

from plotting_results import auc_plot, pr_plot, plot_confusion_matrix

use_gpu = torch.cuda.is_available()
if use_gpu:
    print("Using CUDA")

device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

plt.ion()  

import gc 
gc.enable()

# %%


train_transform = transforms.Compose([
        transforms.Resize((224, 224)),                            
        #transforms.ColorJitter(brightness=0.005, contrast=0.005, saturation=0.005, hue=0.005),
        transforms.RandomChoice([
        transforms.ColorJitter(brightness=0.1),
        transforms.ColorJitter(contrast=0.1), 
        transforms.ColorJitter(saturation=0.1),
        transforms.ColorJitter(hue=0.1)]),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))      
    ])

test_transform = transforms.Compose([
        transforms.Resize((224, 224)),                            
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))      
    ])

# %%

torch.manual_seed(42)
train_fraction = .7
random_state = 2

subset= False

train_batch = 10
test_batch = 1
slide_batch = 1

num_workers = 0
shuffle = False
drop_last = False

train_patches = False
train_slides = True
testing_slides = True

finetuned = False 
embedding_vector_size = 1024

#subtyping = False # (True for 3 class problem) 

# %%

label = 'Pathotype_binary'
patient_id = 'Patient ID'
n_classes=2

if n_classes > 2:
    subtyping=True
else:
    subtyping=False

# %%

file = r"C:\Users\Amaya\Documents\PhD\Data\df_all_stains_patches_labels.csv"
df = pd.read_csv(file, header=0)  
df = df.dropna(subset=[label])

stains = ["CD138", "CD68", "CD20", "HE"]

# %%

file_ids, train_ids, test_ids = Loaders().train_test_ids(df, train_fraction, random_state, patient_id, label, subset)

# %%

CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN, CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST = Loaders().dictionary_loader(df, train_transform, test_transform, train_ids, test_ids, patient_id, label, slide_batch, num_workers)

# %%

# CLAM
# SINGLE STAIN

sys.stdout = open(r"C:\Users\Amaya\Documents\PhD\Data\CLAM_single_stain_results.txt", 'w')
                
if train_slides:
    
    patient_stain_train = [CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN]
    patient_stain_test = [CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST]
       
    for train_stain, test_stain in zip(patient_stain_train, patient_stain_test):
        
        key = list(train_stain.values())[0].dataset.stain[0]
        classification_weights = r"C:/Users/Amaya/Documents/PhD/Data//CLAM_" + key + ".pth"
   
        embedding_net = VGG_embedding(embedding_vector_size=embedding_vector_size, n_classes=n_classes)
        classification_net = GatedAttention(n_classes=n_classes, subtyping=subtyping) # add classification weight variable. 
        
        if use_gpu:
            embedding_net.cuda()
            classification_net.cuda()
        
        loss_fn = nn.CrossEntropyLoss()
        optimizer_ft = optim.Adam(classification_net.parameters(), lr=0.0001)
        
        print(key, flush=True)
        
        _, classification_model = train_att_slides(embedding_net, classification_net, train_stain, test_stain, train_ids, test_ids, loss_fn, optimizer_ft, embedding_vector_size, n_classes=n_classes, bag_weight=0.7, num_epochs=10)
        torch.save(classification_model.state_dict(), classification_weights)
        
sys.stdout.close()        
    
#%%
    
# CLAM
# MULTI STAIN

sys.stdout = open(r"C:\Users\Amaya\Documents\PhD\Data\CLAM_multi_stain_results.txt", 'w')

if train_slides:

    classification_weights = r"C:/Users/Amaya/Documents/PhD/Data//multi_CLAM_classification.pth"
   
    embedding_net = VGG_embedding(embedding_vector_size=embedding_vector_size, n_classes=n_classes)
    classification_net = GatedAttention(n_classes=n_classes, subtyping=subtyping) # add classification weight variable. 
    
    if use_gpu:
        embedding_net.cuda()
        classification_net.cuda()
    
    loss_fn = nn.CrossEntropyLoss()
    optimizer_ft = optim.Adam(classification_net.parameters(), lr=0.0001)
    
    embedding_model, classification_model = train_att_multi_slide(embedding_net, classification_net, train_ids, test_ids,  CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN, CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST, loss_fn, optimizer_ft, embedding_vector_size, n_classes=n_classes, bag_weight=0.7, num_epochs=20)
    torch.save(classification_model.state_dict(), classification_weights)
    
sys.stdout.close()       

# %%

# GRAPH
# SINGLE STAIN

sys.stdout = open(r"C:\Users\Amaya\Documents\PhD\Data\Graph_single_stain_results.txt", 'w')

if train_slides:
    
    patient_stain_train = [CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN]
    patient_stain_test = [CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST]
       
    for train_stain, test_stain in zip(patient_stain_train, patient_stain_test):
        
        key = list(train_stain.values())[0].dataset.stain[0]
        classification_weights = r"C:/Users/Amaya/Documents/PhD/Data//graph_" + key + ".pth"
        
        embedding_net = VGG_embedding(embedding_vector_size=embedding_vector_size, n_classes=n_classes)
        graph_net = GAT_topK(1024) 
        
        if use_gpu:
            embedding_net.cuda()
            graph_net.cuda()
        
        loss_fn = nn.CrossEntropyLoss()
        optimizer_ft = optim.Adam(graph_net.parameters(), lr=0.0001)
        
        print(key, flush=True)

        _, graph_model = train_graph_slides(embedding_net, graph_net, train_stain, test_stain, train_ids, test_ids, loss_fn, optimizer_ft, embedding_vector_size, n_classes=n_classes, num_epochs=10)
        
        torch.save(graph_model.state_dict(), classification_weights)
        
sys.stdout.close()   

 # %%

# GRAPH
# MULTI STAIN

sys.stdout = open(r"C:\Users\Amaya\Documents\PhD\Data\Graph_multi_stain_results.txt", 'w')

if train_slides:
        
    classification_weights = r"C:/Users/Amaya/Documents/PhD/Data//multi_graph_classification.pth"
    
    embedding_net = VGG_embedding(embedding_vector_size=embedding_vector_size, n_classes=n_classes)
    graph_net = GAT_topK(1024) 
    
    if use_gpu:
        embedding_net.cuda()
        graph_net.cuda()
    
    loss_fn = nn.CrossEntropyLoss()
    optimizer_ft = optim.Adam(graph_net.parameters(), lr=0.0001)

    _, graph_model = train_graph_multi_stain(embedding_net, graph_net, CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN, CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST, train_ids, test_ids, loss_fn, optimizer_ft, embedding_vector_size, n_classes=n_classes, num_epochs=20)
    
    torch.save(graph_model.state_dict(), classification_weights)
        
sys.stdout.close()        
    

# %%

# if train_slides:
    
#     embedding_model, classification_model = train_att_slides(embedding_net, classification_net, train_ids, test_ids,  CD138_patients_TRAIN, CD68_patients_TRAIN, CD20_patients_TRAIN, HE_patients_TRAIN, CD138_patients_TEST, CD68_patients_TEST, CD20_patients_TEST, HE_patients_TEST, loss_fn, optimizer_ft, embedding_vector_size, n_classes=n_classes, bag_weight=0.7, num_epochs=10)
#     torch.save(classification_model.state_dict(), classification_weights)



# %%

if testing_slides:
    
    loss_fn = nn.CrossEntropyLoss()
    
    embedding_net = VGG_embedding(embedding_weights, embedding_vector_size=embedding_vector_size, n_classes=n_classes)
    classification_net = GatedAttention(n_classes=n_classes, subtyping=subtyping)

    classification_net.load_state_dict(torch.load(classification_weights), strict=True)
    
    if use_gpu:
        embedding_net.cuda()
        classification_net.cuda()

# %%

if testing_slides:
    
    test_error, test_auc, test_accuracy, test_acc_logger, labels, prob, clsf_report, conf_matrix, sensitivity, specificity, incorrect_preds =       test_slides(embedding_net, classification_net, test_loaded_subsets, loss_fn, n_classes=2)

# %%

target_names=["Fibroid", "M/Lymphoid"]

auc_plot(labels, prob[:, 1], test_auc)
pr_plot(labels, prob[:, 1], sensitivity, specificity)
plot_confusion_matrix(conf_matrix, target_names, title='Confusion matrix', cmap=None, normalize=True)


###############################
# %%

history = soft_vote(embedding_net, test_loaded_subsets)

# %%

