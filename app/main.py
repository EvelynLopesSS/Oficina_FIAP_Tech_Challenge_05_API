import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from app.database import get_db_connection
from app.aws_services import upload_video_to_s3, send_to_sqs, generate_presigned_url

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "hackathon-super-secret")
jwt = JWTManager(app)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = generate_password_hash(data.get('password'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO Usuarios (username, password) VALUES (%s, %s) RETURNING id", (username, password))
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
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM Usuarios WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user and check_password_hash(user[1], password):
        access_token = create_access_token(identity={"id": user[0], "username": username})
        return jsonify(access_token=access_token), 200
    return jsonify({"message": "Credenciais inválidas"}), 401

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_video():
    current_user = get_jwt_identity()
    
    if 'video' not in request.files:
        return jsonify({"error": "Nenhum arquivo de vídeo enviado"}), 400
        
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "Nome de arquivo vazio"}), 400

    # Gera um nome único para não sobrescrever vídeos no S3
    extensao = file.filename.split('.')[-1]
    filename_unico = f"{uuid.uuid4().hex}.{extensao}"
    
    # 1. Faz upload pro S3
    s3_key = upload_video_to_s3(file, filename_unico)
    
    # 2. Salva no Banco de Dados
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO Videos (usuario_id, filename, status, s3_video_key) VALUES (%s, %s, %s, %s) RETURNING id",
        (current_user['id'], file.filename, 'NA_FILA', s3_key)
    )
    video_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    # 3. Manda pra Fila SQS pro Worker processar!
    send_to_sqs(video_id, s3_key, current_user['username'])
    
    return jsonify({"message": "Vídeo recebido com sucesso e enviado para processamento!", "video_id": video_id}), 202

@app.route('/videos', methods=['GET'])
@jwt_required()
def list_videos():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, filename, status, data_upload, s3_zip_key FROM Videos WHERE usuario_id = %s ORDER BY data_upload DESC", (current_user['id'],))
    videos = cur.fetchall()
    cur.close()
    conn.close()
    
    # Se o status for CONCLUIDO, gera a URL de download do ZIP
    for v in videos:
        if v['status'] == 'CONCLUIDO' and v['s3_zip_key']:
            v['download_url'] = generate_presigned_url(v['s3_zip_key'])
        else:
            v['download_url'] = None
            
    return jsonify(videos), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)