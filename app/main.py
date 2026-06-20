import os
import uuid
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from app.database import get_db_connection
from app.aws_services import upload_video_to_s3, send_to_sqs, generate_presigned_url

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "hackathon-super-secret")
jwt = JWTManager(app)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email') 
    password = generate_password_hash(data.get('password'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO Usuarios (username, email, password) VALUES (%s, %s, %s) RETURNING id", (username, email, password))
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Usuário criado!", "id": user_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password, email FROM Usuarios WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            access_token = create_access_token(
                identity=str(user[0]), 
                additional_claims={"username": username, "email": user[2]}
            )
            return jsonify(access_token=access_token), 200
        return jsonify({"error": "Credenciais inválidas"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_video():
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        user_email = claims.get('email') 
        
        if 'video' not in request.files:
            return jsonify({"error": "Nenhum arquivo de vídeo enviado"}), 400
            
        file = request.files['video']
        if file.filename == '':
            return jsonify({"error": "Nome de arquivo vazio"}), 400

        extensao = file.filename.split('.')[-1]
        filename_unico = f"{uuid.uuid4().hex}.{extensao}"
        
        s3_key = upload_video_to_s3(file, filename_unico)
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO Videos (usuario_id, filename, status, s3_video_key) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, file.filename, 'NA_FILA', s3_key)
        )
        video_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        send_to_sqs(video_id, s3_key, user_email) 
        
        return jsonify({"message": "Vídeo recebido com sucesso!", "video_id": video_id}), 202
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/videos', methods=['GET'])
@jwt_required()
def list_videos():
    try:
        user_id = get_jwt_identity() 
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, filename, status, data_upload, s3_zip_key FROM Videos WHERE usuario_id = %s ORDER BY data_upload DESC", (user_id,))
        videos = cur.fetchall()
        cur.close()
        conn.close()
        
        for v in videos:
            if v['status'] == 'CONCLUIDO' and v['s3_zip_key']:
                v['download_url'] = generate_presigned_url(v['s3_zip_key'])
            else:
                v['download_url'] = None
                
        return jsonify(videos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)