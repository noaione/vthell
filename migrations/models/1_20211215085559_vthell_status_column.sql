-- upgrade --
ALTER TABLE "vthelljob" ADD "error" TEXT;
ALTER TABLE "vthelljob" ADD "status" VARCHAR(24) NOT NULL  DEFAULT 'WAITING' /* waiting: WAITING\npreparing: PREPARING\ndownloading: DOWNLOADING\nmuxing: MUXING\nuploading: UPLOAD\ncleaning: CLEANING\ndone: DONE\nerror: ERROR */;
ALTER TABLE "vthelljob" DROP COLUMN "is_downloading";
ALTER TABLE "vthelljob" DROP COLUMN "is_downloaded";
-- downgrade --
ALTER TABLE "vthelljob" ADD "is_downloading" INT NOT NULL  DEFAULT 0;
ALTER TABLE "vthelljob" ADD "is_downloaded" INT NOT NULL  DEFAULT 0;
ALTER TABLE "vthelljob" DROP COLUMN "error";
ALTER TABLE "vthelljob" DROP COLUMN "status";
