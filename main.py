from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import datetime

# 数据库初始化
Base.metadata.create_all(bind=engine)
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- 用户管理 ----------------
@app.post("/users/register")
def register(username: str = Body(...), password: str = Body(...), house_size: float = Body(None), db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(username=username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = models.User(username=username, password=password, house_size=house_size)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"msg": "注册成功", "user_id": user.id}

@app.post("/users/login")
def login(username: str = Body(...), password: str = Body(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=username, password=password).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"msg": "登录成功", "user_id": user.id}

# ---------------- 设备管理 ----------------
@app.post("/devices/")
def add_device(user_id: int = Body(...), name: str = Body(...), type: str = Body(...), db: Session = Depends(get_db)):
    device = models.Device(name=name, type=type, user_id=user_id)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

@app.get("/devices/")
def list_devices(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.Device).filter_by(user_id=user_id).all()

@app.delete("/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(models.Device).get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    db.delete(device)
    db.commit()
    return {"msg": "删除成功"}

# ---------------- 设备使用记录管理 ----------------
@app.post("/usage_records/")
def add_usage_record(device_id: int = Body(...), start_time: str = Body(...), end_time: str = Body(...), energy_consumption: float = Body(None), db: Session = Depends(get_db)):
    record = models.UsageRecord(
        device_id=device_id,
        start_time=pd.to_datetime(start_time),
        end_time=pd.to_datetime(end_time),
        energy_consumption=energy_consumption
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@app.get("/usage_records/")
def list_usage_records(device_id: int, db: Session = Depends(get_db)):
    return db.query(models.UsageRecord).filter_by(device_id=device_id).all()

# ---------------- 安防事件管理 ----------------
@app.post("/security_events/")
def add_security_event(device_id: int = Body(...), event_type: str = Body(...), description: str = Body(None), db: Session = Depends(get_db)):
    event = models.SecurityEvent(
        device_id=device_id,
        event_type=event_type,
        description=description
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@app.get("/security_events/")
def list_security_events(device_id: int, db: Session = Depends(get_db)):
    return db.query(models.SecurityEvent).filter_by(device_id=device_id).all()

# ---------------- 用户反馈管理 ----------------
@app.post("/user_feedbacks/")
def add_feedback(user_id: int = Body(...), content: str = Body(...), rating: int = Body(None), db: Session = Depends(get_db)):
    feedback = models.UserFeedback(
        user_id=user_id,
        content=content,
        rating=rating
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@app.get("/user_feedbacks/")
def list_feedbacks(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.UserFeedback).filter_by(user_id=user_id).all()

# ---------------- 数据分析API ----------------
@app.get("/analytics/usage-frequency")
def usage_frequency(user_id: int, db: Session = Depends(get_db)):
    records = db.query(models.UsageRecord).join(models.Device).filter(models.Device.user_id == user_id).all()
    if not records:
        return {"msg": "无数据"}
    df = pd.DataFrame([{
        "device_id": r.device_id,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "duration": (r.end_time - r.start_time).total_seconds() / 3600
    } for r in records])
    freq = df.groupby("device_id")["duration"].sum()
    plt.figure(figsize=(8,4))
    freq.plot(kind="bar")
    plt.title("设备使用总时长")
    plt.xlabel("设备ID")
    plt.ylabel("小时")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"img_base64": img_b64}

@app.get("/analytics/co-usage")
def co_usage(user_id: int, db: Session = Depends(get_db)):
    records = db.query(models.UsageRecord).join(models.Device).filter(models.Device.user_id == user_id).all()
    if not records:
        return {"msg": "无数据"}
    df = pd.DataFrame([{
        "device_id": r.device_id,
        "start_time": r.start_time,
        "end_time": r.end_time
    } for r in records])
    co_usage_count = {}
    for i, r1 in df.iterrows():
        for j, r2 in df.iterrows():
            if i < j and r1["device_id"] != r2["device_id"]:
                if r1["start_time"] <= r2["end_time"] and r1["end_time"] >= r2["start_time"]:
                    key = tuple(sorted([r1["device_id"], r2["device_id"]]))
                    co_usage_count[key] = co_usage_count.get(key, 0) + 1
    if not co_usage_count:
        return {"msg": "无联动数据"}
    keys = [f"{k[0]}&{k[1]}" for k in co_usage_count.keys()]
    vals = list(co_usage_count.values())
    plt.figure(figsize=(8,4))
    plt.bar(keys, vals)
    plt.title("设备联动次数")
    plt.xlabel("设备对")
    plt.ylabel("次数")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"img_base64": img_b64}

@app.get("/analytics/house-size-impact")
def house_size_impact(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    data = []
    for user in users:
        total_usage = 0
        for device in user.devices:
            for r in device.usage_records:
                total_usage += (r.end_time - r.start_time).total_seconds() / 3600
        if user.house_size:
            data.append({"house_size": user.house_size, "usage": total_usage})
    if not data:
        return {"msg": "无数据"}
    df = pd.DataFrame(data)
    plt.figure(figsize=(8,4))
    plt.scatter(df["house_size"], df["usage"])
    plt.title("房屋面积与设备使用时长")
    plt.xlabel("房屋面积(㎡)")
    plt.ylabel("总使用时长(小时)")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"img_base64": img_b64} 