-- upgrade --
ALTER TABLE "vthellautoscheduler" ADD "chains" JSON;
-- downgrade --
ALTER TABLE "vthellautoscheduler" DROP COLUMN "chains";
