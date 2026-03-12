-- Migration: Add dedicated report columns to ChatbotMessages
-- Date: 2026-03-12
-- Purpose: Store report HTML and report model JSON in dedicated columns
--          instead of embedding them in the Content field with delimiters.

-- Add ReportHtml column (stores the rendered HTML report)
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ChatbotMessages' AND COLUMN_NAME = 'ReportHtml'
)
BEGIN
    ALTER TABLE dbo.ChatbotMessages ADD ReportHtml NVARCHAR(MAX) NULL;
    PRINT 'Added ReportHtml column to ChatbotMessages';
END
ELSE
    PRINT 'ReportHtml column already exists';
GO

-- Add ReportModelJson column (stores the structured report model for editing)
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ChatbotMessages' AND COLUMN_NAME = 'ReportModelJson'
)
BEGIN
    ALTER TABLE dbo.ChatbotMessages ADD ReportModelJson NVARCHAR(MAX) NULL;
    PRINT 'Added ReportModelJson column to ChatbotMessages';
END
ELSE
    PRINT 'ReportModelJson column already exists';
GO

-- Backfill: migrate existing embedded report data to new columns
-- Extract from <!--REPORT_START-->...<!--REPORT_END--> in Content
UPDATE dbo.ChatbotMessages
SET ReportHtml = SUBSTRING(
        Content,
        CHARINDEX('<!--REPORT_START-->', Content) + LEN('<!--REPORT_START-->'),
        CHARINDEX('<!--REPORT_END-->', Content) - CHARINDEX('<!--REPORT_START-->', Content) - LEN('<!--REPORT_START-->')
    )
WHERE Content LIKE '%<!--REPORT_START-->%<!--REPORT_END-->%'
  AND ReportHtml IS NULL;
PRINT 'Backfilled ReportHtml from Content';
GO

-- Extract from <!--REPORT_MODEL_START-->...<!--REPORT_MODEL_END--> in Content
UPDATE dbo.ChatbotMessages
SET ReportModelJson = SUBSTRING(
        Content,
        CHARINDEX('<!--REPORT_MODEL_START-->', Content) + LEN('<!--REPORT_MODEL_START-->'),
        CHARINDEX('<!--REPORT_MODEL_END-->', Content) - CHARINDEX('<!--REPORT_MODEL_START-->', Content) - LEN('<!--REPORT_MODEL_START-->')
    )
WHERE Content LIKE '%<!--REPORT_MODEL_START-->%<!--REPORT_MODEL_END-->%'
  AND ReportModelJson IS NULL;
PRINT 'Backfilled ReportModelJson from Content';
GO

-- Clean up Content field: remove embedded report data (now in dedicated columns)
-- Strip <!--REPORT_START-->...<!--REPORT_END--> from Content
UPDATE dbo.ChatbotMessages
SET Content = LEFT(Content, CHARINDEX('<!--REPORT_START-->', Content) - 1)
           + CASE
                WHEN CHARINDEX('<!--REPORT_END-->', Content) + LEN('<!--REPORT_END-->') <= LEN(Content)
                THEN SUBSTRING(Content, CHARINDEX('<!--REPORT_END-->', Content) + LEN('<!--REPORT_END-->'), LEN(Content))
                ELSE ''
             END
WHERE Content LIKE '%<!--REPORT_START-->%<!--REPORT_END-->%'
  AND ReportHtml IS NOT NULL;
GO

-- Strip <!--REPORT_MODEL_START-->...<!--REPORT_MODEL_END--> from Content
UPDATE dbo.ChatbotMessages
SET Content = LEFT(Content, CHARINDEX('<!--REPORT_MODEL_START-->', Content) - 1)
           + CASE
                WHEN CHARINDEX('<!--REPORT_MODEL_END-->', Content) + LEN('<!--REPORT_MODEL_END-->') <= LEN(Content)
                THEN SUBSTRING(Content, CHARINDEX('<!--REPORT_MODEL_END-->', Content) + LEN('<!--REPORT_MODEL_END-->'), LEN(Content))
                ELSE ''
             END
WHERE Content LIKE '%<!--REPORT_MODEL_START-->%<!--REPORT_MODEL_END-->%'
  AND ReportModelJson IS NOT NULL;
GO

PRINT 'Migration complete: report data moved to dedicated columns.';
GO
