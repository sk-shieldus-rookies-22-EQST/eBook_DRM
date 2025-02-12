#include <iostream>
#include <fstream>
#include <sstream>
#include <cstring>
#include <openssl/evp.h> // AES encryption with OpenSSL
#include <openssl/bio.h> // Base64 encoding/decoding
#include <openssl/buffer.h>
#include <ctime>
#include <aws/core/Aws.h>
#include <aws/s3/S3Client.h>
#include <aws/s3/model/PutObjectRequest.h>
#include <aws/core/auth/AWSCredentials.h>
#include <aws/core/auth/AWSCredentialsProvider.h>
#include <filesystem>
#include <string>
#include <occi.h>

#define AES_KEYLEN 16       // AES key length (128-bit)
#define AES_IVLEN 16        // AES IV length (128-bit)
#define AES_BLOCK_SIZE 16   // AES block size (128-bit)

using namespace std;
using namespace oracle::occi;
namespace fs = std::filesystem;


// Pad AES key and IV to fixed length
void pad_to_length(const string &input, unsigned char *output, size_t length) {
    memset(output, 0, length);
    strncpy(reinterpret_cast<char *>(output), input.c_str(), length);
}

// Read file into memory
unsigned char *read_file(const string &filename, size_t &size) {
    ifstream file(filename, ios::binary | ios::ate);
    if (!file.is_open()) return nullptr;

    size = file.tellg();
    file.seekg(0, ios::beg);

    unsigned char *buffer = new unsigned char[size];
    file.read(reinterpret_cast<char *>(buffer), size);
    file.close();
    return buffer;
}

// Write data to file
bool write_file(const string &filename, unsigned char *data, size_t size) {
    ofstream file(filename, ios::binary);
    if (!file.is_open()) return false;

    file.write(reinterpret_cast<char *>(data), size);
    file.close();
    return true;
}

// AES-128-CBC encryption
bool encrypt_aes(const unsigned char *plaintext, size_t plaintext_len, unsigned char *key, unsigned char *iv,
                 unsigned char **ciphertext, size_t &ciphertext_len) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return false;

    EVP_EncryptInit_ex(ctx, EVP_aes_128_cbc(), nullptr, key, iv);
    *ciphertext = new unsigned char[plaintext_len + AES_BLOCK_SIZE];

    int len;
    EVP_EncryptUpdate(ctx, *ciphertext, &len, plaintext, plaintext_len);
    ciphertext_len = len;

    EVP_EncryptFinal_ex(ctx, *ciphertext + len, &len);
    ciphertext_len += len;

    EVP_CIPHER_CTX_free(ctx);
    return true;
}

// Base64 encoding
string base64_encode(const unsigned char *input, size_t len) {
    BIO *b64 = BIO_new(BIO_f_base64());
    BIO *bio = BIO_new(BIO_s_mem());
    b64 = BIO_push(b64, bio);

    BIO_set_flags(b64, BIO_FLAGS_BASE64_NO_NL);
    BIO_write(b64, input, len);
    BIO_flush(b64);

    BUF_MEM *buffer;
    BIO_get_mem_ptr(b64, &buffer);

    string output(buffer->data, buffer->length);
    BIO_free_all(b64);
    return output;
}


void upload_file(const Aws::String &bucket_name, const Aws::String &object_name, const Aws::String &file_path) {
    // AWS SDK 초기화
    Aws::SDKOptions options;
    Aws::InitAPI(options);
    {
        // AWS 인증 정보 설정
        const Aws::String access_key_id = "AKIAQHFOFEKYX6DM4EWO";         // 액세스 키 ID
        const Aws::String secret_access_key = "E7RW7sVXjl6ZFfjhjVsvHj6KkKthfROsgNX1TOrG"; // 시크릿 액세스 키

        Aws::Auth::AWSCredentials credentials(access_key_id, secret_access_key);

        // 클라이언트 설정 생성
        Aws::Client::ClientConfiguration config;
        config.region = "ap-southeast-2"; // S3 버킷 리전 (예: 서울 리전)

        // S3 클라이언트 생성
        Aws::S3::S3Client s3_client(credentials, config, Aws::Client::AWSAuthV4Signer::PayloadSigningPolicy::Never, false);

        // 파일 업로드 요청 생성
        Aws::S3::Model::PutObjectRequest object_request;
        object_request.SetBucket(bucket_name);
        object_request.SetKey(object_name);

        // 파일 스트림 연결
        auto input_data = Aws::MakeShared<Aws::FStream>("PutObjectInputStream",
                                                        file_path.c_str(),
                                                        std::ios_base::in | std::ios_base::binary);

        if (!input_data->good()) {
            std::cerr << "파일을 열 수 없습니다: " << file_path << std::endl;
            Aws::ShutdownAPI(options);
            return;
        }

        object_request.SetBody(input_data);

        // S3에 파일 업로드
        auto put_object_outcome = s3_client.PutObject(object_request);

        if (put_object_outcome.IsSuccess()) {
            std::cout << "파일 업로드 성공: " << object_name << " to " << bucket_name << std::endl;
        } else {
            std::cerr << "파일 업로드 실패: " << put_object_outcome.GetError().GetMessage() << std::endl;
        }
    }
}


// Insert data into the database
bool insert_into_db(const string &title, const string &auth, const string &summary, const string &reg_date, const string &path, const int price) {
    Environment *env = nullptr;
    Connection *conn = nullptr;
    
    try {
        env = Environment::createEnvironment(Environment::DEFAULT);
        conn = env->createConnection("rookiesAdmin", "eqstAdmin", "dahaezlge-rds.cxv5lcbd6k3e.ap-northeast-2.rds.amazonaws.com:1521/DBookies");
        int year, month, day, id;
        sscanf(reg_date.c_str(), "%d-%d-%d", &year, &month, &day);
        oracle::occi::Date occiDate(env, year, month, day);

        string query = "INSERT INTO book (book_title, book_auth, book_summary, book_reg_date, book_path, book_price) VALUES (:1, :2, :3, :4, :5, :6)";
        
        Statement *stmt = conn->createStatement(query);
        stmt->setString(1, title);
        stmt->setString(2, auth);
        stmt->setString(3, summary);
        stmt->setDate(4, occiDate);
        stmt->setString(5, path);
        stmt->setInt(6, price);
        
        stmt->executeUpdate();
        conn->commit();
        conn->terminateStatement(stmt);

        query = "SELECT book_id FROM book WHERE book_title = :1";
        conn->createStatement(query);
        stmt->setString(1, title);
        
        ResultSet *rs = stmt->executeQuery();
        if (rs->next()) {
            id = rs->getInt(1);
        }
        
        stmt->closeResultSet(rs);
        conn->terminateStatement(stmt);

        string img_path = "/images/book_img/" + to_string(id) + title + ".png";

        query = "UPDATE book SET book_img_path = :1 WHERE book_id = :2";
        conn->createStatement(query);
        stmt->setString(1, img_path);
        stmt->setInt(2, id);
        
        stmt->executeUpdate();
        conn->commit();
        conn->terminateStatement(stmt);
        
        env->terminateConnection(conn);
        Environment::terminateEnvironment(env);
        
        return true;
    } catch (SQLException &e) {
        cerr << "DB Error: " << e.getMessage() << endl;
        if (conn) env->terminateConnection(conn);
        if (env) Environment::terminateEnvironment(env);
        return false;
    }
}

int main() {
    string book_title, book_auth, book_summary, reg_date, input_path, output_path, price;

    // User input
    cout << "책 제목: "; getline(cin, book_title);
    cout << "저자: "; getline(cin, book_auth);
    cout << "줄거리: "; getline(cin, book_summary);
    cout << "출간일: "; getline(cin, reg_date);
    cout << "가격: "; getline(cin, price);
    int book_price = std::stoi(price);

    if (reg_date == "") reg_date = "2025-01-01";

    // File paths
    input_path = "/home/ubuntu/books/" + book_title + ".pdf";

    // Base64 encode file name
    string base64_input = book_title + "|" + book_auth + "|" + reg_date;
    string base64_encoded = base64_encode(reinterpret_cast<const unsigned char *>(base64_input.c_str()), base64_input.size());
    output_path = base64_encoded + ".encrypted";

    // AES encryption setup
    unsigned char key[AES_KEYLEN], iv[AES_IVLEN], *plaintext = nullptr, *ciphertext = nullptr;
    size_t plaintext_len, ciphertext_len;
    pad_to_length("ROOKIES", key, AES_KEYLEN);
    pad_to_length("EQST", iv, AES_IVLEN);

    // File read and encryption
    plaintext = read_file(input_path, plaintext_len);
    if (!plaintext || !encrypt_aes(plaintext, plaintext_len, key, iv, &ciphertext, ciphertext_len) ||
        !write_file(output_path, ciphertext, ciphertext_len)) {
        cerr << "파일 처리 실패" << endl;
        delete[] plaintext;
        delete[] ciphertext;
        return 1;
    }

    const Aws::String bucket_name = "dahaezulge-bucket";
    const Aws::String object_name = output_path;
    const Aws::String file_path = "./" + output_path;

    upload_file(bucket_name, object_name, file_path);

    try {

        // 삭제할 파일의 전체 경로 생성
        fs::path file_path = "./" + output_path;

        // 파일 삭제
        if (fs::exists(file_path) && fs::is_regular_file(file_path)) {
            fs::remove(file_path);
            std::cout << "파일이 삭제되었습니다: " << file_path << std::endl;
        } else {
            std::cout << "파일을 찾을 수 없거나 파일이 아닙니다: " << file_path << std::endl;
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "오류 발생: " << e.what() << std::endl;
        return 1;
    }

    // Insert data into DB
    if (!insert_into_db(book_title, book_auth, book_summary, reg_date, output_path, book_price)) {
        cerr << "DB 저장 실패" << endl;
        delete[] plaintext;
        delete[] ciphertext;
        return 1;
    }

    // Success message
    cout << "성공적으로 저장되었습니다: " << output_path << endl;
    delete[] plaintext;
    delete[] ciphertext;
    return 0;
}
