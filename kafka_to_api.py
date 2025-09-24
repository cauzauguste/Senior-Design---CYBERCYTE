import os, asyncio, json, ssl
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer
from motor.motor_asyncio import AsyncIOMotorClient

# Configure using environment variables for connection security parameters
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "osquery_logs")
KAFKA_CA_FILE = os.getenv("KAFKA_CA_FILE")
KAFKA_CERT_FILE = os.getenv("KAFKA_CERT_FILE")
KAFKA_KEY_FILE = os.getenv("KAFKA_KEY_FILE")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_CA_FILE = os.getenv("MONGO_CA_FILE")

DB_NAME = "osquery_data"
COLLECTION_NAME = "host_telemetry"

db_client: AsyncIOMotorClient | None = None

# Kafka Consumer + MongoDB Logic 
async def consume_kafka_messages():
    """Consumes messages from Kafka and saves them to MongoDB."""
    
    # Configure Kafka TLS/SSL 
    kafka_consumer_args = {
        'bootstrap_servers': KAFKA_BROKER,
        'value_deserializer': lambda v: json.loads(v.decode('utf-8')),
        'auto_offset_reset': 'latest',
        'enable_auto_commit': True,
        'group_id': 'fastapi-mongo-consumer',
    }
    
    # If environment variables are set, add SSL parameters
    if KAFKA_CA_FILE and KAFKA_CERT_FILE and KAFKA_KEY_FILE:
        kafka_consumer_args.update({
            'security_protocol': 'SSL',
            'ssl_context': ssl.create_default_context(cafile=KAFKA_CA_FILE),
            'ssl_check_hostname': False,
            'ssl_certfile': KAFKA_CERT_FILE,
            'ssl_keyfile': KAFKA_KEY_FILE,
        })
    consumer = KafkaConsumer(KAFKA_TOPIC, **kafka_consumer_args)
    print("Starting Kafka consumer...")

    if not db_client:
        print("MongoDB client not initialized. Cannot save data.")
        return
    db = db_client[DB_NAME]
    collection = db[COLLECTION_NAME]

    for message in consumer:
        try:
            osquery_log_entry = message.value
            osquery_log_entry['timestamp_processed'] = datetime.utcnow()
            await collection.insert_one(osquery_log_entry)
            print(f"Successfully saved document from host: {osquery_log_entry.get('hostIdentifier')}")
        except Exception as e:
            print(f"Error processing or saving message to MongoDB: {e}")

# Manage FastAPI App Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client
    print("Connecting to MongoDB...")
    
    # Configure MongoDB TLS/SSL 
    mongodb_client_args = {
        'uuidRepresentation': 'standard',
    }
    
    # If configured for MongoDB, add ssl parameters
    if MONGO_CA_FILE:
        mongodb_client_args.update({
            'ssl': True,
            'ssl_ca_certs': MONGO_CA_FILE,
        })
    db_client = AsyncIOMotorClient(MONGO_URI, **mongodb_client_args)
    print("MongoDB connection established.")
    
    # Kafka consumer starts as background task
    task = asyncio.create_task(consume_kafka_messages())
    yield
    
    # Shutdown cleans up resources
    print("Closing MongoDB connection...")
    db_client.close()
    print("MongoDB connection closed.")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Kafka consumer task cancelled.")

# Initialize FastAPI 
app = FastAPI(lifespan=lifespan)

# API endpoints 
@app.get("/telemetry")
async def get_all_telemetry():
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection not available.")
    
    db = db_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    data = []
    async for doc in collection.find().sort("timestamp_processed", -1).limit(100):
        doc['_id'] = str(doc['_id'])
        data.append(doc)
    return {"telemetry_data": data}

@app.get("/telemetry/count")
async def get_telemetry_count():
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection not available.")
    
    db = db_client[DB_NAME]
    collection = db[COLLECTION_NAME]
    count = await collection.count_documents({})
    return {"count": count}