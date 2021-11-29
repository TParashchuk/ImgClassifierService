from joblib import load
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os
import json
import zipfile
import shutil

from kafka import KafkaConsumer
from kafka import KafkaProducer

from google.cloud import storage
from google.oauth2 import service_account

bootstrap_servers = os.environ['SERVICE_IP'].split() #['35.202.7.6:9092']
topicName = os.environ['TOPIC_NAME'] #'topic-2'
categories = os.environ['CATEGORIES'].split() #['Orange','Violet','Yellow','Red','Blue','Green','Brown','Black']
gcp_json_credentials_dict = json.loads(os.environ['CREDENTIALS'])

consumer = KafkaConsumer (topicName, bootstrap_servers = bootstrap_servers) 
producer = KafkaProducer (bootstrap_servers = bootstrap_servers)

def upload_blob(source_file_name, destination_blob_name):
    
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
 
    print(
       "Blob {} uploaded to storage successfully ".format(
            source_file_name, destination_blob_name
        )
    )

def download_blob(source_blob_name, destination_file_name):
    
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
 
    print(
        "Blob {} downloaded to file path {} successfully ".format(
            source_blob_name, destination_file_name
        )
    )

def run_service(name_file):
    IMG_SZ = 100
    directory = os.path.splitext(name_file)[0]

    download_blob(name_file, name_file)
    
    with zipfile.ZipFile(name_file,"r") as zip_ref:
        zip_ref.extractall(r"")
    
    for dirname, _, filenames in os.walk(os.path.splitext(name_file)[0]):
        for filename in filenames:
            os.path.join(dirname,filename)
    
    print("Start of image classification...")
    
    data=[]
    for filename in os.listdir(directory):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            img = cv2.imread(os.path.join(directory,filename))
            img_resize=cv2.resize(img,(IMG_SZ,IMG_SZ))
            
            l=[img_resize.flatten()]

            model = load('predictor.joblib')
            probability=model.predict_proba(l)
        
            json_response=[]
            for ind,val in enumerate(categories):
                json_response.append({'color': val, 'probability': str(probability[0][ind]*100) + "%" })

            data.append({'image': filename, 'predictedColor': categories[model.predict(l)[0]], 'predictedColorDetail': json_response})
        else:
            continue

    os.remove(name_file)
    shutil.rmtree(directory, ignore_errors=True)
    return data


if __name__== "__main__":

    while True:
        print("Service started")
        print(100*"*")

        name_file = ''
        for msg in consumer:
            message = msg.value.decode('UTF-8')

            if os.path.isfile('predictor.joblib') and '.zip' in message:
                name_file = message
                
                credentials = service_account.Credentials.from_service_account_info(gcp_json_credentials_dict)
                
                storage_client = storage.Client(project=gcp_json_credentials_dict['project_id'], credentials=credentials)
                bucket = storage_client.bucket("open-horizon-storage")
                
                json_data = run_service(name_file)
                
                name_result_file = "ResultColorClassified-{}.json".format(
                            os.path.splitext(name_file)[0]
                        )
                
                with open(name_result_file, 'w') as f:
                        json.dump(json_data, f, indent=4)
                
                upload_blob(name_result_file, name_result_file);
                producer.send(topicName, ("Images were classified. The result is saved to a file {} on the GCP".format(name_result_file)).encode('UTF-8'))

                os.remove(name_result_file)

                print("Images were classified. The result is saved to a file on the GCP")
                print(100*"*")

            if not os.path.isfile('predictor.joblib') and '.zip' in message:
                name_file = message
                producer.send(topicName, b'File *.joblib not found')
                print("File *.joblib not found")
                print(100*"*")

            else:
                continue
                
               