-- =====================================================
-- QRZ VIBE CORE DATABASE SCHEMA
-- USERS + USER PHOTOS + SUBSCRIPTIONS
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    gender ENUM('male', 'female', 'non-binary', 'other') DEFAULT NULL,
    birth_date DATE NOT NULL,
    bio TEXT DEFAULT NULL,
    location_lat DECIMAL(9,6) DEFAULT NULL,
    location_lon DECIMAL(9,6) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS user_photos (
    photo_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    photo_url VARCHAR(500) NOT NULL,
    is_profile_picture BOOLEAN DEFAULT FALSE,
    display_order INT DEFAULT 0,
    visibility ENUM('public', 'matches', 'private') DEFAULT 'public',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_photos_user_id (user_id),
    INDEX idx_user_photos_profile_picture (is_profile_picture),
    INDEX idx_user_photos_display_order (display_order),

    CONSTRAINT fk_user_photos_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    sub_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    plan_name ENUM('free', 'premium', 'vip') DEFAULT 'free',
    status ENUM('active', 'expired', 'cancelled') DEFAULT 'active',
    start_date DATE DEFAULT NULL,
    end_date DATE DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_subscriptions_user_id (user_id),
    INDEX idx_subscriptions_plan_name (plan_name),
    INDEX idx_subscriptions_status (status),

    CONSTRAINT fk_subscriptions_user
        FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);