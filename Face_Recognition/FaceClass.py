import cv2
import face_recognition
import numpy as np

class FaceClass:

    def __init__(self) -> None:
        self.face_encodings = []

    def train_faces(self,new_face_data):
        face_ids = []
        for image_path in new_face_data:
            image = cv2.imread(image_path)
            face_locations = face_recognition.face_locations(image)
            if len(face_locations) == 1:
                face_encoding = face_recognition.face_encodings(image, face_locations)[0]
                self.face_encodings.append(face_encoding)
                # Assign an id to the face
                face_id = len(self.face_encodings) - 1
                face_ids.append(face_id)
        return face_ids
    
    def check_face(self,image_path):
        image = cv2.imread(image_path)
        face_locations = face_recognition.face_locations(image)
        if len(face_locations) == 1:
            face_encoding = face_recognition.face_encodings(image, face_locations)[0]
            # Compare the face encoding with all the saved encodings
            matches = face_recognition.compare_faces(self.face_encodings, face_encoding)
            if True in matches:
                # Return the id of the first matching face
                return matches.index(True)
        return None