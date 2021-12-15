-- upgrade --
CREATE TABLE IF NOT EXISTS "vthellautoscheduler" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "type" SMALLINT NOT NULL  /* channel: 1\ngroup: 2\nword: 3\nregex_word: 4 */,
    "data" TEXT NOT NULL,
    "chains" JSON,
    "include" INT NOT NULL  DEFAULT 1
);
CREATE TABLE IF NOT EXISTS "vthelljob" (
    "id" VARCHAR(128) NOT NULL  PRIMARY KEY,
    "title" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "resolution" VARCHAR(24),
    "start_time" BIGINT NOT NULL,
    "channel_id" TEXT NOT NULL,
    "member_only" INT NOT NULL  DEFAULT 0,
    "status" VARCHAR(24) NOT NULL  DEFAULT 'WAITING' /* waiting: WAITING\npreparing: PREPARING\ndownloading: DOWNLOADING\nmuxing: MUXING\nuploading: UPLOAD\ncleaning: CLEANING\ndone: DONE\nerror: ERROR */,
    "last_status" VARCHAR(24)   /* waiting: WAITING\npreparing: PREPARING\ndownloading: DOWNLOADING\nmuxing: MUXING\nuploading: UPLOAD\ncleaning: CLEANING\ndone: DONE\nerror: ERROR */,
    "error" TEXT
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(20) NOT NULL,
    "content" JSON NOT NULL
);
