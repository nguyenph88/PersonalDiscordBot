#!/usr/bin/env python3
"""
PostgreSQL Connection Test Script
Tests connection to PostgreSQL database using credentials from .env file
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import time

class PostgresConnectionTester:
    """Test class for PostgreSQL connection"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get database configuration from environment
        self.db_config = {
            'host': os.getenv('VIRTUAL_TRADER_DATABASE_HOST', '10.0.0.104'),
            'port': int(os.getenv('VIRTUAL_TRADER_DATABASE_PORT', 5432)),
            'database': os.getenv('VIRTUAL_TRADER_DATABASE_NAME', 'fastapi_db'),
            'user': os.getenv('VIRTUAL_TRADER_DATABASE_USER', 'postgres'),
            'password': os.getenv('VIRTUAL_TRADER_DATABASE_PASSWORD', 'VerySecurePassword123'),
            'sslmode': 'prefer'  # Try SSL but allow non-SSL fallback
        }
        
        print("🔍 Database Configuration:")
        for key, value in self.db_config.items():
            if key == 'password':
                print(f"  {key}: {'*' * len(str(value)) if value else 'None'}")
            else:
                print(f"  {key}: {value}")
        print()
    
    def test_basic_connection(self):
        """Test basic connection without SSL"""
        print("🔌 Testing Basic Connection (no SSL)...")
        
        # Remove SSL mode for basic test
        test_config = self.db_config.copy()
        test_config.pop('sslmode', None)
        
        try:
            conn = psycopg2.connect(**test_config)
            print("✅ Basic connection successful!")
            
            # Test basic query
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print(f"📊 PostgreSQL Version: {version[0]}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Basic connection failed: {e}")
            return False
    
    def test_ssl_connection(self):
        """Test connection with SSL"""
        print("\n🔒 Testing SSL Connection...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            print("✅ SSL connection successful!")
            
            # Test basic query
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print(f"📊 PostgreSQL Version: {version[0]}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ SSL connection failed: {e}")
            return False
    
    def test_connection_options(self):
        """Test different connection options"""
        print("\n🔧 Testing Different Connection Options...")
        
        # Test 1: No SSL, no timeout
        print("  Testing: No SSL, no timeout")
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                connect_timeout=10
            )
            print("    ✅ Success")
            conn.close()
        except Exception as e:
            print(f"    ❌ Failed: {e}")
        
        # Test 2: No SSL, with timeout
        print("  Testing: No SSL, with timeout")
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                connect_timeout=30
            )
            print("    ✅ Success")
            conn.close()
        except Exception as e:
            print(f"    ❌ Failed: {e}")
        
        # Test 3: Force no SSL
        print("  Testing: Force no SSL")
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                sslmode='disable',
                connect_timeout=10
            )
            print("    ✅ Success")
            conn.close()
        except Exception as e:
            print(f"    ❌ Failed: {e}")
    
    def test_network_connectivity(self):
        """Test basic network connectivity"""
        print("\n🌐 Testing Network Connectivity...")
        
        import socket
        
        try:
            # Test if we can resolve the hostname
            print(f"  Resolving hostname: {self.db_config['host']}")
            ip = socket.gethostbyname(self.db_config['host'])
            print(f"    ✅ Resolved to: {ip}")
            
            # Test if we can connect to the port
            print(f"  Testing port connection: {self.db_config['host']}:{self.db_config['port']}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((ip, self.db_config['port']))
            sock.close()
            
            if result == 0:
                print("    ✅ Port is reachable")
            else:
                print(f"    ❌ Port is not reachable (error code: {result})")
                
        except Exception as e:
            print(f"    ❌ Network test failed: {e}")
    
    def test_database_operations(self):
        """Test basic database operations"""
        print("\n🗄️ Testing Database Operations...")
        
        try:
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                sslmode='disable',
                connect_timeout=10
            )
            
            with conn.cursor() as cursor:
                # Test 1: Check if tables exist
                print("  Testing: Check existing tables")
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cursor.fetchall()
                if tables:
                    print(f"    ✅ Found {len(tables)} tables:")
                    for table in tables:
                        print(f"      - {table[0]}")
                else:
                    print("    ℹ️ No tables found (database is empty)")
                
                # Test 2: Create a test table
                print("  Testing: Create test table")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS connection_test (
                        id SERIAL PRIMARY KEY,
                        test_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        message TEXT
                    )
                """)
                print("    ✅ Test table created/verified")
                
                # Test 3: Insert test data
                print("  Testing: Insert test data")
                cursor.execute("""
                    INSERT INTO connection_test (message) 
                    VALUES (%s)
                """, ("Connection test successful",))
                print("    ✅ Test data inserted")
                
                # Test 4: Query test data
                print("  Testing: Query test data")
                cursor.execute("SELECT * FROM connection_test ORDER BY id DESC LIMIT 1")
                result = cursor.fetchone()
                print(f"    ✅ Query successful: {result}")
                
                # Test 5: Clean up test table
                print("  Testing: Clean up test table")
                cursor.execute("DROP TABLE connection_test")
                print("    ✅ Test table cleaned up")
            
            conn.commit()
            conn.close()
            print("    ✅ All database operations successful!")
            
        except Exception as e:
            print(f"    ❌ Database operations failed: {e}")
    
    def run_all_tests(self):
        """Run all connection tests"""
        print("🚀 Starting PostgreSQL Connection Tests")
        print("=" * 50)
        
        # Test network connectivity first
        self.test_network_connectivity()
        
        # Test basic connection
        basic_success = self.test_basic_connection()
        
        # Test SSL connection
        ssl_success = self.test_ssl_connection()
        
        # Test different connection options
        self.test_connection_options()
        
        # Test database operations if basic connection works
        if basic_success:
            self.test_database_operations()
        
        print("\n" + "=" * 50)
        print("📋 Test Summary:")
        print(f"  Basic Connection: {'✅ Success' if basic_success else '❌ Failed'}")
        print(f"  SSL Connection: {'✅ Success' if ssl_success else '❌ Failed'}")
        
        if basic_success:
            print("  🎉 Database is accessible and working!")
        else:
            print("  ⚠️ Database connection failed. Check your configuration.")
            print("\n💡 Troubleshooting Tips:")
            print("  1. Verify the host and port are correct")
            print("  2. Check if the database server is running")
            print("  3. Verify username and password")
            print("  4. Check firewall settings")
            print("  5. Try different SSL modes")

def main():
    """Main function"""
    try:
        tester = PostgresConnectionTester()
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

