-- Suggested indexes to improve pinyin recall performance.
-- These are not applied automatically; run them manually against your Postgres database.

-- HWXNet characters: speed up zibiao_index range scans used by build_session_queue.
CREATE INDEX IF NOT EXISTS idx_hwxnet_characters_zibiao_index
    ON hwxnet_characters (zibiao_index);

-- Feng characters: support lookups by character for learning/meaning data.
CREATE INDEX IF NOT EXISTS idx_feng_characters_character
    ON feng_characters (character);

-- Pinyin recall character bank: speed up per-user lookups and updates.
CREATE INDEX IF NOT EXISTS idx_pinyin_recall_character_bank_user_id
    ON pinyin_recall_character_bank (user_id);

-- Pinyin recall character bank: optional composite index if you often filter by user + next_due_utc.
CREATE INDEX IF NOT EXISTS idx_pinyin_recall_character_bank_user_due
    ON pinyin_recall_character_bank (user_id, next_due_utc);

