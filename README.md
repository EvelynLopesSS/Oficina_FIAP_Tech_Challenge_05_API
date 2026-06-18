# ⚙️ Hackathon Fase 5 - Backend API (Repo 3 de 5)

Este repositório contém a **API REST (Flask)** responsável por receber as requisições dos usuários no Sistema de Processamento de Vídeos da FIAP X. 

Adotando uma arquitetura **Orientada a Eventos**, esta API atende ao requisito rigoroso de **"não perder requisições em caso de picos"**. Em vez de processar os vídeos sincronicamente (o que causaria timeout), ela atua como um *Ingestion Layer*.

## 🎯 Responsabilidades
- **Autenticação:** Cadastro e Login de usuários utilizando JWT.
- **Upload Seguro:** Recebe o arquivo `.mp4` do Frontend e realiza o upload imediato e seguro para o **Amazon S3**.
- **Persistência de Estado:** Registra o vídeo no **Amazon RDS (PostgreSQL)** com o status inicial `NA_FILA`.
- **Desacoplamento:** Publica uma mensagem na fila **Amazon SQS**, notificando os *Workers* de que um novo vídeo está pronto para processamento.
- **Presigned URLs:** Gera URLs temporárias do S3 para permitir que o usuário faça o download do `.zip` processado com segurança.

## 🚀 Como Executar o Deploy
O deploy é 100% automatizado no Kubernetes (EKS) via GitHub Actions.

1. Configure os seguintes **Secrets** no repositório:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
   - `DB_HOST`, `DB_NAME`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`
   - `JWT_SECRET` (Uma chave forte para os tokens)
   - `S3_BUCKET_NAME` (O output gerado pelo Repo 2 - Infra K8s)
   - `SQS_QUEUE_URL` (O output gerado pelo Repo 2 - Infra K8s)
   - `ECR_REPO` (URL do repositório ECR da API, gerada no Repo 2)
2. Faça um push na branch `main`. A pipeline irá criar as tabelas no RDS, gerar a imagem Docker e atualizar o cluster.