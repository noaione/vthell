-- upgrade --
ALTER TABLE "vthellautoscheduler" RENAME COLUMN "enabled" TO "include";
-- downgrade --
ALTER TABLE "vthellautoscheduler" RENAME COLUMN "include" TO "enabled";
