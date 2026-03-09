-- =============================================================================
-- usp_Chatbot_GetTicketTimeline
-- Returns ticket counts grouped by time period for trend charts.
-- Pre-aggregated data — the chatbot gets compact rows, not individual tickets.
--
-- Follows the same pattern as usp_Chatbot_GetTicketSummary for user/role/filter logic.
--
-- Usage:
--   EXEC usp_Chatbot_GetTicketTimeline @Username='admin'
--   EXEC usp_Chatbot_GetTicketTimeline @Username='admin', @Period='week'
--   EXEC usp_Chatbot_GetTicketTimeline @Username='admin', @ProjectNames='Arab National Bank', @Period='month'
--   EXEC usp_Chatbot_GetTicketTimeline @Username='admin', @DateFrom='2025-11-01', @DateTo='2026-02-28'
--
-- Run this in SSMS against the TickTraq database to create the procedure.
-- =============================================================================

USE [TickTraq]
GO

IF OBJECT_ID('dbo.usp_Chatbot_GetTicketTimeline', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_Chatbot_GetTicketTimeline
GO

CREATE PROCEDURE [dbo].[usp_Chatbot_GetTicketTimeline]
    @Username       NVARCHAR(100),
    @ProjectNames   NVARCHAR(MAX)   = NULL,
    @TeamNames      NVARCHAR(MAX)   = NULL,
    @RegionNames    NVARCHAR(MAX)   = NULL,
    @Period         NVARCHAR(20)    = 'month',   -- 'week', 'month', 'quarter', 'year'
    @DateFrom       DATE            = NULL,
    @DateTo         DATE            = NULL,
    @Top            INT             = 500,
    @TaskTypeNames  NVARCHAR(MAX)   = NULL    -- NEW: "PM", "TR", "Other", or "PM,TR"
AS
BEGIN
    SET NOCOUNT ON;

    -- Default date range: last 12 months if not specified
    IF @DateFrom IS NULL
        SET @DateFrom = DATEADD(MONTH, -12, GETDATE())
    IF @DateTo IS NULL
        SET @DateTo = CAST(GETDATE() AS DATE)

    -- =========================================================================
    -- Step 1: Get user (same pattern as usp_Chatbot_GetTicketSummary)
    -- =========================================================================
    DECLARE @UserId INT, @EmployeeId INT;

    SELECT @UserId = Id, @EmployeeId = EmployeeId
    FROM Users
    WHERE Username = @Username AND ISNULL(IsDeleted, 0) = 0;

    IF @UserId IS NULL
    BEGIN
        SELECT NULL AS Period, 0 AS TicketsCreated, 0 AS TicketsCompleted, 'User not found' AS Message;
        RETURN;
    END

    -- =========================================================================
    -- Step 2: Get user's teams with roles (same as Summary SP)
    -- =========================================================================
    DECLARE @UserTeams TABLE (
        TeamId INT,
        TeamName NVARCHAR(200),
        ProjectId INT,
        ProjectName NVARCHAR(200),
        RoleId INT,
        RegionId INT,
        RegionName NVARCHAR(200)
    );

    INSERT INTO @UserTeams (TeamId, TeamName, ProjectId, ProjectName, RoleId, RegionId, RegionName)
    SELECT DISTINCT
        t.Id AS TeamId,
        t.Name AS TeamName,
        t.ProjectId,
        p.Name AS ProjectName,
        tr.RoleId,
        t.RegionId,
        sp.Name AS RegionName
    FROM dbo.TeamRoleUsers tru
    INNER JOIN dbo.TeamRoles tr ON tr.Id = tru.TeamRoleId
    INNER JOIN dbo.Teams t ON t.Id = tr.TeamId
    INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
    LEFT JOIN dbo.StateProvince sp ON sp.Id = t.RegionId
    WHERE tru.UserId = @UserId
      AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
      AND tr.IsActive = 1 AND ISNULL(tr.IsDeleted, 0) = 0
      AND t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
      AND p.IsActive = 1 AND ISNULL(p.IsDeleted, 0) = 0;

    -- =========================================================================
    -- Step 3: Parse comma-separated filters (same as Summary SP)
    -- =========================================================================
    DECLARE @SelectedProjects TABLE (ProjectId INT, ProjectName NVARCHAR(200));
    IF @ProjectNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedProjects (ProjectId, ProjectName)
        SELECT DISTINCT ut.ProjectId, ut.ProjectName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@ProjectNames, ',') s
        WHERE ut.ProjectName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END

    DECLARE @SelectedTeams TABLE (TeamId INT, TeamName NVARCHAR(200));
    IF @TeamNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedTeams (TeamId, TeamName)
        SELECT DISTINCT ut.TeamId, ut.TeamName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@TeamNames, ',') s
        WHERE ut.TeamName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END

    DECLARE @SelectedRegions TABLE (RegionId INT, RegionName NVARCHAR(200));
    IF @RegionNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedRegions (RegionId, RegionName)
        SELECT DISTINCT ut.RegionId, ut.RegionName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@RegionNames, ',') s
        WHERE ut.RegionName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END

    -- =========================================================================
    -- Step 3b: Parse comma-separated task type names
    -- =========================================================================
    DECLARE @SelectedTaskTypes TABLE (TaskTypeId INT, TaskTypeName NVARCHAR(200));
    IF @TaskTypeNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedTaskTypes (TaskTypeId, TaskTypeName)
        SELECT DISTINCT lc.Id, lc.Name
        FROM LookupChild lc
        INNER JOIN LookupMaster lm ON lm.Id = lc.LookupMasterId
        CROSS APPLY STRING_SPLIT(@TaskTypeNames, ',') s
        WHERE lm.Name = 'Task Type'
          AND lc.Name LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END

    -- =========================================================================
    -- Step 4: Build filtered teams list
    -- =========================================================================
    DECLARE @CanViewAll BIT = CASE WHEN EXISTS (SELECT 1 FROM @UserTeams WHERE RoleId IN (1,6,7)) THEN 1 ELSE 0 END;
    DECLARE @IsSupervisor BIT = CASE WHEN EXISTS (SELECT 1 FROM @UserTeams WHERE RoleId = 4) THEN 1 ELSE 0 END;

    DECLARE @FilteredTeams TABLE (TeamId INT);

    INSERT INTO @FilteredTeams (TeamId)
    SELECT DISTINCT TeamId
    FROM @UserTeams ut
    WHERE
        (@TeamNames IS NULL OR ut.TeamId IN (SELECT TeamId FROM @SelectedTeams))
        AND (@ProjectNames IS NULL OR ut.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
        AND (@RegionNames IS NULL OR ut.RegionId IN (SELECT RegionId FROM @SelectedRegions));

    -- =========================================================================
    -- Step 5: Aggregate by requested period
    -- =========================================================================
    SELECT TOP (@Top)
        CASE @Period
            WHEN 'week'    THEN FORMAT(DATEADD(DAY, -(DATEPART(WEEKDAY, t.ReportedDate) - 1), t.ReportedDate), 'yyyy-MM-dd')
            WHEN 'month'   THEN FORMAT(t.ReportedDate, 'yyyy-MM')
            WHEN 'quarter' THEN CONCAT(YEAR(t.ReportedDate), '-Q', DATEPART(QUARTER, t.ReportedDate))
            WHEN 'year'    THEN CAST(YEAR(t.ReportedDate) AS NVARCHAR(4))
            ELSE FORMAT(t.ReportedDate, 'yyyy-MM')
        END AS Period,

        COUNT(*) AS TicketsCreated,

        SUM(CASE WHEN t.CompletedDate IS NOT NULL THEN 1 ELSE 0 END) AS TicketsCompleted

    FROM dbo.Tickets t
    WHERE
        t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
        AND t.ReportedDate IS NOT NULL
        AND CAST(t.ReportedDate AS DATE) >= @DateFrom
        AND CAST(t.ReportedDate AS DATE) <= @DateTo
        AND t.TeamId IN (SELECT TeamId FROM @FilteredTeams)
        AND (@ProjectNames IS NULL OR t.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
        AND (@TaskTypeNames IS NULL OR t.TaskTypeId IN (SELECT TaskTypeId FROM @SelectedTaskTypes))
        AND (@CanViewAll = 1 OR t.EmployeeId = @EmployeeId OR (@IsSupervisor = 1 AND t.CallStatusId = 9))
    GROUP BY
        CASE @Period
            WHEN 'week'    THEN FORMAT(DATEADD(DAY, -(DATEPART(WEEKDAY, t.ReportedDate) - 1), t.ReportedDate), 'yyyy-MM-dd')
            WHEN 'month'   THEN FORMAT(t.ReportedDate, 'yyyy-MM')
            WHEN 'quarter' THEN CONCAT(YEAR(t.ReportedDate), '-Q', DATEPART(QUARTER, t.ReportedDate))
            WHEN 'year'    THEN CAST(YEAR(t.ReportedDate) AS NVARCHAR(4))
            ELSE FORMAT(t.ReportedDate, 'yyyy-MM')
        END
    ORDER BY Period ASC

END
GO

-- =============================================================================
-- Test it
-- =============================================================================
-- EXEC usp_Chatbot_GetTicketTimeline @Username = 'admin'
-- EXEC usp_Chatbot_GetTicketTimeline @Username = 'admin', @Period = 'week'
-- EXEC usp_Chatbot_GetTicketTimeline @Username = 'admin', @ProjectNames = 'Arab National Bank', @Period = 'month'
-- EXEC usp_Chatbot_GetTicketTimeline @Username = 'admin', @DateFrom = '2025-11-01', @DateTo = '2026-02-28', @Period = 'week'
