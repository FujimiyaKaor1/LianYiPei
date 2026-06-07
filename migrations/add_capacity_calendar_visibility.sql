-- 添加产能日历公开范围字段
-- 执行时间: 2024-12-08

-- 为 enterprises 表添加 capacity_calendar_visibility 字段
ALTER TABLE enterprises 
ADD COLUMN capacity_calendar_visibility VARCHAR(20) DEFAULT 'private' 
COMMENT '产能日历公开范围: public/partners/private';

-- 为现有记录设置默认值
UPDATE enterprises 
SET capacity_calendar_visibility = 'private' 
WHERE capacity_calendar_visibility IS NULL;

-- 添加索引以提高查询性能
CREATE INDEX idx_capacity_calendar_visibility 
ON enterprises(capacity_calendar_visibility);
