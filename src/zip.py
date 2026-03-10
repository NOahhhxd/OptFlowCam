import zipfile
from random import randint
import os 
import pyperclip as pc

class ZipUtilities:
    @staticmethod
    def toZip(file, filename):
        zip_file = zipfile.ZipFile(filename, 'w')
        if os.path.isfile(file):
            zip_file.write(file)
        else:
            ZipUtilities.addFolderToZip(zip_file, file)
        zip_file.close()

    @staticmethod
    def addFolderToZip(zip_file, folder): 
        for file in os.listdir(folder):
            full_path = os.path.join(folder, file)
            if os.path.isfile(full_path):
                # print 'File added: ' + str(full_path)
                zip_file.write(full_path)
            elif os.path.isdir(full_path):
                # print 'Entering folder: ' + str(full_path)
                ZipUtilities.addFolderToZip(zip_file, full_path)

current_path = os.getcwd()
current_files = os.listdir(current_path)
filename = f"optFlowCam{randint(0,99999)}.zip"
while filename in current_files:
	filename = f"optFlowCam{randint(0,99999)}.zip"
	
# optFlowPath = os.path.join(current_path, "optFlowCam")
ZipUtilities.toZip("optFlowCam", filename)

pc.copy(os.path.join(current_path, filename))
print(filename)