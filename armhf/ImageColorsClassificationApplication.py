import matplotlib.pyplot as plt
import cv2
import numpy as np
import pandas as pd
import os
import json
import zipfile
import shutil

from kafka import KafkaConsumer
from kafka import KafkaProducer

from google.cloud import storage
from google.oauth2 import service_account

from tqdm import tqdm
from joblib import dump,load

bootstrap_servers = os.environ['TRAIN_SERVICE_IP'].split() #['35.202.7.6:9092']
topicName = os.environ['TRAIN_TOPIC_NAME'] #'topic-1'
categories = os.environ['CATEGORIES'].split() #['Orange','Violet','Yellow','Red','Blue','Green','Brown','Black']
gcp_json_credentials_dict = json.loads(os.environ['CREDENTIALS'])

consumer = KafkaConsumer (topicName, bootstrap_servers = bootstrap_servers)
producer = KafkaProducer (bootstrap_servers = bootstrap_servers)

IMG_SZ = 100

trn_data = []

def download_blob(bucket_name, source_blob_name, destination_file_name):

    storage_client = storage.Client(project=gcp_json_credentials_dict['project_id'], credentials=credentials)
 
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
 
    print(
        "Blob {} downloaded to file path {}. successfully ".format(
            source_blob_name, destination_file_name
        )
    )

def create_training_data(name_file):
    for cat in categories:
        path=os.path.join(os.path.splitext(name_file)[0],cat)
        class_num=categories.index(cat)
        if os.path.isdir(path):
            for img in os.listdir(path):
                try:
                    img_arr=cv2.imread(os.path.join(path,img))
                    new_arr=cv2.resize(img_arr,(IMG_SZ,IMG_SZ))
                    trn_data.append([new_arr,class_num])
                except Exception as e:
                    pass

if __name__== "__main__":

    while True:
        print("Train service started")
        print(100*"*")
        
        for msg in consumer:
            message = msg.value.decode('UTF-8')

            if '.zip' in message:
                name_file = message
                credentials = service_account.Credentials.from_service_account_info(gcp_json_credentials_dict)
                
                download_blob("open-horizon-storage", name_file, name_file)
                
                with zipfile.ZipFile(name_file,"r") as zip_ref:
                    zip_ref.extractall(r"")
                
                for dirname, _, filenames in os.walk(os.path.splitext(name_file)[0]):
                    for filename in filenames:
                        os.path.join(dirname,filename)
                
                create_training_data(name_file)
                
                setlen = len(trn_data)
                print(setlen)
                
                X=[]
                y=[]
                
                for categories, label in trn_data:
                    X.append(categories)
                    y.append(label)
                X = np.array(X).reshape(setlen,-1)
                
                X.shape
                
                X=X/255.0
                
                y=np.array(y)
                
                y.shape
                
                from sklearn.model_selection import train_test_split
                X_train, X_test, y_train, y_test =train_test_split(X,y)
                
                
                from sklearn.svm import SVC
                svc = SVC(kernel='linear',gamma='auto',probability=True)
                svc.fit(X_train,y_train)
                
                y2=svc.predict(X_test)
                
                from sklearn.metrics import accuracy_score
                print( 'Accuracy is', accuracy_score(y_test,y2))
                
                from sklearn.metrics import classification_report
                print('Classification Report',classification_report(y_test,y2))
                
                result = pd.DataFrame({'original' : y_test, 'predicted' : y2})
                
                print(result)
                
                dump(svc,'predictor.joblib')
                producer.send(topicName, b'File *.joblib was got')
                print(100*"*")

                os.remove(name_file)
                shutil.rmtree(os.path.splitext(name_file)[0], ignore_errors=True)

            else:
                continue
