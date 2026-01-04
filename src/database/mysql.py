# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from contextlib import contextmanager
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# =========================
# MySQL 연결 설정 (.env에서 로드)
# =========================
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}

def get_connection():
    """MySQL 연결 생성"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        print(f"✅ MySQL 연결 성공: {MYSQL_CONFIG['database']}")
        return conn
    except Error as e:
        print(f"❌ MySQL 연결 실패: {e}")
        raise


class MySQLDatabase:
    """MySQL 데이터베이스 연결 및 관리 클래스"""

    def __init__(self):
        self.config = MYSQL_CONFIG
        self.connection: Optional[mysql.connector.MySQLConnection] = None

    def connect(self):
        """MySQL 서버에 연결"""
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connection = get_connection()
            return self.connection
        except Error as e:
            print(f"❌ MySQL 연결 실패: {e}")
            raise

    def disconnect(self):
        """MySQL 연결 종료"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("✅ MySQL 연결 종료")

    @contextmanager
    def get_cursor(self):
        """커서를 반환하는 컨텍스트 매니저"""
        connection = self.connect()
        cursor = connection.cursor(dictionary=True)
        try:
            yield cursor
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"❌ 트랜잭션 롤백: {e}")
            raise
        finally:
            cursor.close()

    def execute_query(self, query: str, params: tuple = None):
        """SELECT 쿼리 실행"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def execute_update(self, query: str, params: tuple = None):
        """INSERT, UPDATE, DELETE 실행"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.rowcount

    def init_tables(self):
        """테이블 초기화"""
        with self.get_cursor() as cursor:
            # users 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)

            # chats 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) DEFAULT '새 채팅',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # messages 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    chat_id INT NOT NULL,
                    role ENUM('user', 'assistant') NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                    INDEX idx_chat_id (chat_id),
                    INDEX idx_created_at (created_at)
                )
            """)

            print("✅ 테이블 초기화 완료")

# 전역 인스턴스
db = MySQLDatabase()
