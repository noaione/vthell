-- upgrade --
CREATE TABLE IF NOT EXISTS "vthelljobchattemporary" (
    "id" VARCHAR(128) NOT NULL  PRIMARY KEY,
    "filename" TEXT NOT NULL,
    "channel_id" TEXT NOT NULL,
    "member_only" INT NOT NULL  DEFAULT 0
);
-- downgrade --
DROP TABLE IF EXISTS "vthelljobchattemporary";
