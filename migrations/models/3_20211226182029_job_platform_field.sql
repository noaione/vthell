-- upgrade --
ALTER TABLE "vthelljob" ADD "platform" VARCHAR(24) NOT NULL  DEFAULT 'youtube' /* YouTube: youtube\nTwitch: twitch\nTwitter: twitter\nTwitcasting: twitcasting */;
-- downgrade --
ALTER TABLE "vthelljob" DROP COLUMN "platform";
