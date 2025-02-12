from flask import Flask, request, jsonify
import boto3
from botocore.exceptions import ClientError
import os
import oracledb
import base64

app = Flask(__name__)

S3_BUCKET_NAME = 'dahaezulge-bucket'
S3_EXPIRES_IN = 3600

DB_CONFIG = {
    "host": "dahaezlge-rds.cxv5lcbd6k3e.ap-northeast-2.rds.amazonaws.com",
    "port": 1521,
    "user": "rookiesAdmin",
    "password": "eqstAdmin",
    "service_name": "DBookies"
}

def get_db_connection():
    dsn = oracledb.makedsn(DB_CONFIG["host"], DB_CONFIG["port"], service_name=DB_CONFIG["service_name"])
    return oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"], dsn=dsn)

S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'YOUR_ACCESS_KEY')  
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'YOUR_SECRET_KEY')  

@app.route('/generate-presigned-url', methods=['POST'])
def generate_presigned_url():
    connection = None

    try:
        client_data = request.get_json()
        if not client_data:
            return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

        user_id = client_data.get('user_id')
        book_id = client_data.get('book_id')

        if not user_id or not book_id:
            return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = :1", [user_id])
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

        cursor.execute("SELECT book_id, book_title, book_auth, book_path FROM book WHERE book_id = :1", [book_id])
        book = cursor.fetchone()
        if not book or not book[3]:
            return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

        book_path = book[3]

        cursor.execute("SELECT * FROM purchase WHERE purchase_user_id = :1 AND purchase_book_id = :2", [user_id, book_id])
        purchase = cursor.fetchone()
        if not purchase:
            return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

    except Exception:
        return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

    finally:
        if connection:
            connection.close()

    s3 = boto3.client(
        's3',
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name='ap-southeast-2'
    )

    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': book_path},
            ExpiresIn=S3_EXPIRES_IN
        )
    except ClientError:
        return jsonify({"error": "요청 정보가 올바르지 않습니다."}), 400

    return jsonify({
        "message": "Presigned URL generated successfully.",
        "presigned_url": presigned_url
    })

@app.route('/get-key', methods=['GET'])
def get_key():
    fixed_aes_iv = b'\x52\x4f\x4f\x4b\x49\x45\x53'
    fixed_aes_key = b'\x45\x51\x53\x54'

    return jsonify({
        "aes_key": base64.b64encode(fixed_aes_key).decode('utf-8'),
        "aes_iv": base64.b64encode(fixed_aes_iv).decode('utf-8')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
