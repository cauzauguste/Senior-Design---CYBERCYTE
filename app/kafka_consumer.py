import asyncio
from aiokafka import AIOKafkaConsumer
from app.database import db
import json
from app.config import KAFKA_URI, KAFKA_TOPIC

async def start_kafka_consumer():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_URI,
        security_protocol="SSL",  # enable TLS
        ssl_cafile="certificates/ca-cert.pem",
        ssl_certfile="certificates/client-cert.pem",
        ssl_keyfile="certificates/client-key.pem"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data = json.loads(msg.value)
            # Save telemetry to MongoDB
            await db.telemetry.insert_one(data)
    finally:
        await consumer.stop()
