-- 1. 建立單字資料表
CREATE TABLE IF NOT EXISTS words (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    unit TEXT,
    word TEXT,
    pos TEXT,
    definition TEXT,
    sentence TEXT,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(unit, word, pos)
);

-- 2. 建立使用者資料表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 啟用 RLS（只有持有 Secret Key 的後端才能存取）
ALTER TABLE words ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 4. 建立存取政策（允許 service_role 完全存取）
CREATE POLICY "Allow all for service_role" ON words
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all for service_role" ON users
  FOR ALL USING (true) WITH CHECK (true);

-- 5. 建立測驗結果紀錄表
CREATE TABLE IF NOT EXISTS quiz_results (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    mode TEXT NOT NULL,          -- 'quiz' (選中文), 'reverse' (選英文), 'spelling' (拼字)
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    accuracy FLOAT NOT NULL,     -- 正確率 (0 ~ 100)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. 啟用 RLS
ALTER TABLE quiz_results ENABLE ROW LEVEL SECURITY;

-- 7. 建立存取政策（允許 service_role 完全存取）
DROP POLICY IF EXISTS "Allow all for service_role" ON quiz_results;
CREATE POLICY "Allow all for service_role" ON quiz_results
  FOR ALL USING (true) WITH CHECK (true);

-- 8. 建立系統設定資料表
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. 啟用 RLS
ALTER TABLE system_config ENABLE ROW LEVEL SECURITY;

-- 10. 建立系統設定存取政策
DROP POLICY IF EXISTS "Allow all for service_role" ON system_config;
CREATE POLICY "Allow all for service_role" ON system_config
  FOR ALL USING (true) WITH CHECK (true);

----測試用
-- 1. 先清除 W52 單元原有的所有單字
DELETE FROM words WHERE unit = 'W52';
-- 2. 在 W52 中只新增一個測試單字
INSERT INTO words (unit, word, pos, definition, sentence) 
VALUES ('W52', 'apple', 'n.', '蘋果', 'I like to eat a red apple.');