# -*- coding: utf-8 -*-
import uvicorn
import shutil
from fastapi import FastAPI, Query, Request, status, Response, Header, Body, File, UploadFile
from pydantic import BaseModel, Field
from datetime import datetime,timedelta
from fastapi.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from loguru import logger
from dotenv import load_dotenv
from os.path import join, dirname
from Face_Recognition.FaceClass import load_model,save_model,get_encoding_dummy_data
import sqlite3


#conn = sqlite3.connect('sqllite3.db')

import traceback
import os

logger.add(".\API Backend\log\EveSpy_API.log", rotation="100MB", retention="1 year")

dot_env_path = join(dirname(__file__), '.env')
load_dotenv(dot_env_path)
APP_ENV = os.environ.get("APP_ENV")

app = FastAPI(
    title='EyeSpy',
    description='Control API',
    version='0.1.1'
    #docs_url=None, 
    #redoc_url=None
)

class rt_building(BaseModel):
    building_id : int = Field(..., title="building_id", description="building id for new building", example= 123)

class rt_resident(BaseModel):
    resident_id : int = Field(..., title="resident_id", description="resident id for new resident", example= 123)

class rt_session(BaseModel):
    session_token : str = Field(..., title="session_token", description="session token", example= "ABC123")

class ACK(BaseModel):
    status : str = Field(..., title="status", description="status of request", example= "Failure")

class BuildingInfo(BaseModel):
    name : str = Field(...,  title="name", description="name of Building", example= "farzad")
    address : str = Field(...,  title="address", description="address of Building", example= "123 abc")
    alert_type : int = Field(..., title="alert_type", description="alert on/off/all", example= 1)
    alertEmail : str = Field(...,  title="alertEmail", description="Email for alerts", example= "farzad@gmail.com")

class ResidentInfo(BaseModel):
    name : str = Field(...,  title="name", description="name of person", example= "farzad")
    building_id : int = Field(..., title="building_id", description="Id of Building", example= 123456)
    appartment_no : int = Field(..., title="appartment_no", description="no of appartment", example= 420)
    images : list[str]

class rt_BuildingInfo(BaseModel):
    list_building : list[BuildingInfo]

class rt_ResidentInfo(BaseModel):
    list_resident : list[ResidentInfo]

def db_connection():
    connection = sqlite3.connect("sqllite3.db")
    connection.row_factory = sqlite3.Row
    return connection

def check_session(conn,session_token):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM SESSION_DETAIL where SESSION_ID ='{session_token}'")
    rows = cur.fetchall()
    if rows == []:
        return False
    else:
        VALID_TILL = dict(rows[0])['VALID_TILL']
        if datetime.strptime(VALID_TILL,"%Y-%m-%d %H:%M:%S") > datetime.now():

            # update the session token
            valid_till = datetime.now() + timedelta(minutes=10)
            conn.execute(f"""UPDATE SESSION_DETAIL SET VALID_TILL = '{valid_till.strftime("%Y-%m-%d %H:%M:%S")}' WHERE SESSION_ID={session_token}""")
            conn.commit()

            return True
        else:
            return False


@app.post('/api/SecurityCheck', summary="Security Check Endpoint", response_model=ACK)
def SecurityCheck(
        camera_ip: str = Header(..., description= "ip of camera"),
        face_image: str = Header(..., description= "image of the face")     
        ):
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT AUTH_BUILDING_ID from CAMERA_INDEX where CAM_IP='{camera_ip}'")
        rows = cur.fetchall()
        if rows == []:
            conn.close()
            return JSONResponse(status_code=500,content={"ACK":"Invalid Camera"})
        
        building_id = rows[0]['AUTH_BUILDING_ID']
        
        tmp_img_path = dirname(__file__) + f'\\tmp\\{camera_ip}_{building_id}.jpg'
        with open(tmp_img_path,'wb') as tmp_file:
            tmp_file.writelines(eval(face_image))
        
        model = load_model()
        face_id = model.check_face(tmp_img_path)

        if face_id == None:

            return JSONResponse(status_code=200,content={"ACK":"Access denied"})
        else:
            sql = f"""select * from IMAGE_INDEX ii inner join RESIDENT_DETAILS rd 
                        on ii.RESIDENT_ID = rd.RESIDENT_ID 
                        where ii.IMAGE_ID = {face_id} and rd.BUILDING_ID = {building_id}"""
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            if rows == []:
                return JSONResponse(status_code=200,content={"ACK":"Access denied (STAKLER -_- )"})
            else:
                os.remove(tmp_img_path)
               
    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    
    return JSONResponse(status_code=200,content={"ACK":"Access Granted"})
    
@app.get('/api/get_session', summary="get the access token for the admin functions",response_model=rt_session)
def get_session(       
        admin_user: str = Header(..., description= "user name"),
        adminm_password: str = Header(..., description= "password")
        ):
    try:
        conn = db_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM USER_DETAILS where USER_NAME='{admin_user}' and PASSWORD='{adminm_password}'")
        rows = cur.fetchall()
        if rows == []:
            conn.close()
            return JSONResponse(status_code=404,content={"massage":"Invalid Credentials"})
        else:
            time_now = datetime.now() 
            valid_till = time_now + timedelta(minutes=10)
            conn.execute(f"""INSERT INTO SESSION_DETAIL (CREATED_AT, VALID_TILL, USER_NAME)VALUES('{time_now.strftime("%Y-%m-%d %H:%M:%S")}', '{valid_till.strftime("%Y-%m-%d %H:%M:%S")}','{admin_user}')""")
            row_id = conn.execute("select last_insert_rowid() as id").fetchall()    
            session_token = dict(row_id[0])['id']
            conn.commit()
            conn.close()
    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    
    return JSONResponse(status_code=200,content={"session_token":session_token})

@app.put('/admin/Add_resident', summary="add new people to an building", response_model=rt_resident)
def Add_resident(
        User: ResidentInfo,
        session_token: str = Header(..., description= "token for the admin functions")
        ):
    try:
        conn = db_connection()
        if not check_session(conn,session_token):
            conn.close()
            return JSONResponse(status_code=404,content={"massage":"Invalid Session"})
        sql = f"""INSERT INTO RESIDENT_DETAILS (NAME, BUILDING_ID, HOUSE_NO)VALUES('{User.name}', {User.building_id}, {User.appartment_no})"""
        conn.execute(sql)
        row_id = conn.execute("select last_insert_rowid() as id").fetchall()    
        RESIDENT_ID = dict(row_id[0])['id']
        conn.commit()
        
        #downloading the images 
        tmp_dir_path = dirname(__file__) + f'\\tmp\\{RESIDENT_ID}' 
        os.mkdir(tmp_dir_path)
        image_count=1
        image_path_list = []
        for image in User.images:
            image_path_list.append(f"{tmp_dir_path}\\{image_count}.jpg")
            with open(f"{tmp_dir_path}\\{image_count}.jpg",'wb') as tmp_file:
                tmp_file.writelines(eval(image))
            image_count+=1

        #Opencv work
        model = load_model()
        ids = model.train_faces(image_path_list)
        save_model(model)

        # storing_model_id to database
        for _id in ids:
            sql = f"""INSERT INTO IMAGE_INDEX(IMAGE_ID, RESIDENT_ID)VALUES({_id} , {RESIDENT_ID});"""
            conn.execute(sql)
        
        conn.commit()
        conn.close()
        shutil.rmtree(tmp_dir_path)

    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    return JSONResponse(status_code=200,content={"resident_id":RESIDENT_ID})

@app.delete("/admin/remove_resident", summary="remove people from building", response_model=ACK)
def remove_resident(
        session_token: str = Header(..., description= "token for the admin functions"),
        building_id : int = Header(..., description= "Id of Building"),
        resident_id : int = Header(..., description= "Id of Resident")
        ):
    conn = db_connection()
    if not check_session(conn,session_token):
        conn.close()
        return JSONResponse(status_code=404,content={"massage":"Invalid Session"})
    try:
        # delete from RESIDENT_DETAILS table
        sql = f"""DELETE FROM RESIDENT_DETAILS WHERE RESIDENT_ID={resident_id}"""
        conn.execute(sql)

        ## delete from model
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM IMAGE_INDEX where RESIDENT_ID ='{resident_id}'")
        rows = cur.fetchall()

        model = load_model()
        for row in rows:
            index = row['IMAGE_ID']
            model.face_encodings[index] = get_encoding_dummy_data()
        save_model(model)

        # delete from IMAGE_INDEX table
        sql = f"""DELETE FROM IMAGE_INDEX WHERE RESIDENT_ID={resident_id}"""
        conn.execute(sql)
        conn.commit()
        conn.close()

    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})

    return JSONResponse(status_code=200,content={"ACK":"Deleted"})

@app.put('/admin/Add_building', summary="add new building", response_model=rt_building)
def Add_building(
        BuildingInfo: BuildingInfo ,
        session_token: str = Header(..., description= "token for the admin functions")
        ):
    try:
        conn = db_connection()
        if not check_session(conn,session_token):
            conn.close()
            return JSONResponse(status_code=404,content={"massage":"Invalid Session"})

        time_now = datetime.now() 
        sql = f"""INSERT INTO BUILDING_DETAILS (NAME, ADDRESS, AUTH_USER, NO_OF_RESIDENT, NO_OF_CAMERAS, CREATED_AT, ALERT_TYPE) 
                VALUES('{BuildingInfo.name}', '{BuildingInfo.address}', 
                (select USER_NAME from SESSION_DETAIL WHERE SESSION_ID = {session_token}), 
                0, 0, '{time_now.strftime("%Y-%m-%d %H:%M:%S")}', {BuildingInfo.alert_type}) """
        conn.execute(sql)
        row_id = conn.execute("select last_insert_rowid() as id").fetchall()    
        BUILDING_ID = dict(row_id[0])['id']
        conn.commit()
        conn.close()
    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    return JSONResponse(status_code=200,content={"building id":BUILDING_ID})

@app.get('/admin/list_building', summary="list of all building",response_model=rt_BuildingInfo)
def list_building(
        session_token: str = Header(..., description= "token for the admin functions"),
        ):
    try:
        conn = db_connection()
        if not check_session(conn,session_token):
            conn.close()
            return JSONResponse(status_code=404,content={"massage":"Invalid Session"})

        sql = f"""select USER_NAME from SESSION_DETAIL WHERE SESSION_ID = {session_token}"""
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        user_name = rows[0]['USER_NAME']
        sql = f"""select * from BUILDING_DETAILS WHERE AUTH_USER = '{user_name}'"""
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        list_building = [dict(x) for x in rows]
    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    
    return JSONResponse(status_code=200,content= {"list_building":list_building} )

@app.get('/admin/list_resident', summary="list of all resident",response_model=rt_ResidentInfo)
def list_resident(
        session_token: str = Header(..., description= "token for the admin functions"),
        ):
    try:
        conn = db_connection()
        if not check_session(conn,session_token):
            conn.close()
            return JSONResponse(status_code=404,content={"massage":"Invalid Session"})
        
        sql = f"""SELECT rd.* from BUILDING_DETAILS bd inner join RESIDENT_DETAILS rd 
                on bd.BUILDING_ID = rd.BUILDING_ID 
                where bd.AUTH_USER = (select USER_NAME from SESSION_DETAIL WHERE SESSION_ID = {session_token})"""
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        list_resident = [dict(x) for x in rows]
    except sqlite3.Error as error:
        logger.error("Error in add_resident function",error,traceback.print_exc())
        conn.rollback()
        conn.close()
        return JSONResponse(status_code=500,content={"massage":f"Internal Server error {error}"})
    return JSONResponse(status_code=200,content= {"list_resident": list_resident})

@app.get('/my-endpoint')
async def my_endpoint(request: Request):
    return {'status': 1, 'message': request.client.host}


if __name__ == "__main__":

    if APP_ENV == 'local' :
        uvicorn.run(app, host="127.0.0.1", port=8000)
    elif APP_ENV == 'testing' :
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        uvicorn.run(app, host="0.0.0.0", port=80)
