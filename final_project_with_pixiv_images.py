# -*- coding: utf-8 -*-
"""Final Project with Pixiv Images.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1zgwPzqJ6zxk3Mt5rP7XkQLbqw8zNaHE4

# COMP 576: Deep Learning: Fine-tuning CLIP Model for Anime Image Retrieval   

 Haodong Qi(hq9), Jiaxin Li(jl260), Wanrong Cai(wc52), Yi Zhang(yz180)

## Experiment Setup
"""

!pip install -U "finetuner[full]"
# !pip install gdown
!pip install --upgrade --no-cache-dir gdown
!pip install git+https://github.com/openai/CLIP.git

pip install -U --no-cache-dir gdown --pre

"""We got image datasets by crawling from Pixiv and downloading from Kaggle dataset. We have also seperated the dataset into two parts. `data` is the dataset which we download from website, and `data_kaggle` is the dataset which we downloaded from kaggle website. """

# data crawled from Pixiv
!gdown https://drive.google.com/uc?id=1oISqsmmVgdhZ6GaLu4fFpyzoYgnegYVP
!gdown https://drive.google.com/uc?id=1UPMU4i7lCscJCiDjKHc_W6BCAwTb_uvW
!gdown https://drive.google.com/uc?id=1A1Af99GkmlHKXf7opo0OVS6l-Rcgrl8I
!gdown https://drive.google.com/uc?id=1wM3xZymHsoyYExRy1keG0S0pu-O_MEJ9

!unzip /content/Albedo_Cleaned.zip 
!unzip /content/Ayaka_Cleaned.zip
!unzip /content/Hu_Tao_Cleaned.zip
!unzip /content/Kokomi_Cleaned.zip

# data from Kaggle
!gdown https://drive.google.com/uc?id=1INXxKx8C2zl6scd528gMuzGMouKJ-eJv
!gdown https://drive.google.com/uc?id=1nKAYrMu7aBxJQiQ8GmazL3iC8JYe95hB
!gdown https://drive.google.com/uc?id=1E96kIyeiKPlz8cqjzQ_62iQiZ2BDOa76
!gdown https://drive.google.com/uc?id=1_l-uPtl4zycUFN0qVark7K-Aam9WNhjR
!gdown https://drive.google.com/uc?id=1tcIxV41Ww8AAlxXcZvcNMsK1GLU_ispV

!unzip /content/Albedo_Kaggle.zip
!unzip /content/Ayaka_Kaggle.zip
!unzip /content/Hu_Tao_Kaggle.zip
!unzip /content/Kokomi_Kaggle.zip
!unzip /content/Neither_Kaggle.zip

!ls

"""# CLIP Zero-Shot

## Data
"""

from docarray import Document, DocumentArray
import torch
import clip
from PIL import Image

# Cleaned Pixiv dataset
data = DocumentArray.from_files(['/content/Albedo_Cleaned/*.*', '/content/Ayaka_Cleaned/*.*', '/content/Hu_Tao_Cleaned/*.*', '/content/Kokomi_Cleaned/*.*'])
# Kaggle dataset
kaggle_data = DocumentArray.from_files(['/content/Albedo_Kaggle/*.*', '/content/Ayaka_Kaggle/*.*', '/content/Hu_Tao_Kaggle/*.*', '/content/Kokomi_Kaggle/*.*', '/content/Neither_Kaggle/*.*'])
model, preprocess = clip.load("ViT-B/32", device="cuda" if torch.cuda.is_available() else "cpu")

# uncomment to use kaggle_data instead of Pixiv data.
# data = kaggle_data

# label the image
def create_label(doc: Document):
    temp_label = doc.uri.split('/')[2].split('_')
    doc.tags['label'] = ' '.join(temp_label[0:len(temp_label)-1])
    return doc

import math

data.apply(create_label, show_progress=True)

data = data.shuffle()
# train-test-split ratio
train_ratio = 0.5
# data_size = len(data)
data_size = 2000
cut_off_point = math.floor(data_size * train_ratio)

training_data = data[:cut_off_point]
testing_data = data[cut_off_point:data_size]

# check data
data

# pre-process images
def prepare_image(doc: Document):
    doc.tensor = preprocess(Image.open(doc.uri)).unsqueeze(0).to("cuda" if torch.cuda.is_available() else "cpu")
    doc.embedding = model.encode_image(doc.tensor).cpu().detach().numpy().squeeze()
    doc.pop('tensor')
    return doc

# pre-process text
def prepare_text(doc: Document):
    doc.tensor = clip.tokenize(doc.text).to("cuda" if torch.cuda.is_available() else "cpu")
    doc.embedding = model.encode_text(doc.tensor).cpu().detach().numpy().squeeze()
    doc.pop('tensor')
    return doc

testing_data.apply(prepare_image, show_progress=True)

"""## Modeling & Testing
We construct four text queries about the Genshin Impact characters. The four queries are following:  
 `Albedo fighting`,   
 `Ayaka dancing`,   
 `Hu Tao standing`,   
 `Kokomi underwater`.  
"""

# Test that displays top 10 matching results of the input query.
def test_zero_shot_model(query: str):
  # setup query and doucment array
  query_array = DocumentArray([Document(content=query)])
  # display the top 10 matches
  print(f'Query: {query}')
  query_array.apply(prepare_text).match(testing_data, metric='cosine', limit=10)
  for idx, match in enumerate(query_array[0].matches):
      print(f'Position {idx}: {match.tags["label"]}')
      match.display()

test_zero_shot_model('Albedo fighting')

test_zero_shot_model('Ayaka dancing')

test_zero_shot_model('Hu Tao standing')

test_zero_shot_model('Kokomi underwater')

"""## Zero-Shot Result

 `Albedo fighting`: 0%,  
 `Ayaka dancing`: 50%,  
 `Hu Tao standing`: 20%,   
 `Kokomi underwater`: 70%.

This result does not meet our expectations, so we should try to get better result by fine-tuning the CLIP model.

# CLIP Fine-tuning

We fine-tune the CLIP model with the Finetuner services by JinaAI.

Documentation can be found at: https://finetuner.jina.ai/

## Fine-tuning Process
"""

import finetuner

# Jina AI login
finetuner.login(force=True)

# initialize a DocumentArray as final training data.
finetuner_training_dataset = DocumentArray()

for doc in training_data:
    finetuner_training_data = Document()
    img_chunk = doc.load_uri_to_image_tensor(224, 224)
    img_chunk.modality = 'image'
    txt_chunk = Document(content=doc.tags['label'])
    txt_chunk.modality = 'text'
    finetuner_training_data.chunks.extend([img_chunk, txt_chunk])
    finetuner_training_dataset.append(finetuner_training_data)

# Check pairs
finetuner_training_dataset[0]
# finetuner_training_dataset[100]
# finetuner_training_dataset[1000]

# run finetuner
run = finetuner.fit(
    model='openai/clip-vit-base-patch32',
    train_data=finetuner_training_dataset,   
    learning_rate=1e-5,
    loss='CLIPLoss',
    cpu=False,
)

# track the job
for log in run.stream_logs():
    print(log)

# save artifacts to local
artifact = run.save_artifact('/content/')

# use clip_image_encoder and clip_text_encoder models to optimize the clip loss jointly.
clip_text_encoder = finetuner.get_model(artifact=artifact, select_model='clip-text')
clip_image_encoder = finetuner.get_model(artifact=artifact, select_model='clip-vision')

finetuner.encode(model=clip_image_encoder, data=testing_data)

"""## Fine-tuning & Testing"""

# Test that displays top 10 matching results of the input query.
def test_fine_tuned_model(query: str):
  # setup query and doucment array
  query_docs = DocumentArray([Document(content=query)])
  finetuner.encode(model=clip_text_encoder, data=query_docs)
  # display top 10 matches
  print(f'Query: {query}')
  query_docs.match(testing_data, metric='cosine', limit=10)
  for idx, match in enumerate(query_docs[0].matches):
      print(f'Position {idx}: {match.tags["label"]}')
      match.display()

test_fine_tuned_model('Albedo fighting')

test_fine_tuned_model('Ayaka dancing')

test_fine_tuned_model('Hu Tao standing')

test_fine_tuned_model('Kokomi underwater')

"""## Fine-tuning Result

 `Albedo fighting`: 80%,  
 `Ayaka dancing`: 80%,  
 `Hu Tao standing`: 90%,   
 `Kokomi underwater`: 90%.

The accuracy of the query results significantly improved after fine-tuning the CLIP model.
"""