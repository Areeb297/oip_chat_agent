USE [TickTraq]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER PROCEDURE [dbo].[usp_Chatbot_GetEngineerPerformance]
(
    @Username NVARCHAR(100),
    @EmployeeNames NVARCHAR(MAX) = NULL,      -- Comma-separated, partial match on FirstName + LastName
    @ProjectNames NVARCHAR(MAX) = NULL,        -- Comma-separated project names
    @TeamNames NVARCHAR(MAX) = NULL,           -- Comma-separated team names
    @RegionNames NVARCHAR(MAX) = NULL,         -- Comma-separated region/province names
    @Month INT = NULL,                         -- 1-12
    @Year INT = NULL,                          -- 2020-2030
    @DateFrom DATE = NULL,                     -- Start date filter
    @DateTo DATE = NULL,                       -- End date filter
    @IncludeActivity BIT = 0,                   -- 1 = include DailyActivityLog breakdown (3rd result set)
    @RoleNames NVARCHAR(MAX) = NULL             -- Comma-separated role names to filter (e.g. "Field Engineer,Resident Engineer")
                                                 -- NULL = defaults to field-level roles only (Field Engineer, Resident Engineer)
                                                 -- "All" = no role filter, show everyone
)
AS
BEGIN
    SET NOCOUNT ON;

    -- =========================================
    -- VALIDATE USER
    -- =========================================
    DECLARE @UserId INT, @EmployeeId INT;

    SELECT @UserId = Id, @EmployeeId = EmployeeId
    FROM Users
    WHERE Username = @Username AND ISNULL(IsDeleted, 0) = 0;

    IF @UserId IS NULL
    BEGIN
        SELECT 0 AS TotalEngineers, 'User not found' AS Message;
        RETURN;
    END

    -- =========================================
    -- ROLE-BASED ACCESS
    -- =========================================
    DECLARE @UserTeams TABLE (
        TeamId INT,
        TeamName NVARCHAR(200),
        ProjectId INT,
        ProjectName NVARCHAR(200),
        RoleId INT
    );

    INSERT INTO @UserTeams (TeamId, TeamName, ProjectId, ProjectName, RoleId)
    SELECT DISTINCT
        t.Id AS TeamId,
        t.Name AS TeamName,
        t.ProjectId,
        p.Name AS ProjectName,
        tr.RoleId
    FROM dbo.TeamRoleUsers tru
    INNER JOIN dbo.TeamRoles tr ON tr.Id = tru.TeamRoleId
    INNER JOIN dbo.Teams t ON t.Id = tr.TeamId
    INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
    WHERE tru.UserId = @UserId
      AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
      AND tr.IsActive = 1 AND ISNULL(tr.IsDeleted, 0) = 0
      AND t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
      AND p.IsActive = 1 AND ISNULL(p.IsDeleted, 0) = 0;

    -- RoleId 1=Admin, 6=PM, 7=Supervisor can view all
    DECLARE @CanViewAll BIT = CASE
        WHEN EXISTS (SELECT 1 FROM @UserTeams WHERE RoleId IN (1,6,7)) THEN 1
        ELSE 0
    END;

    -- =========================================
    -- PROJECT FILTER
    -- =========================================
    DECLARE @SelectedProjects TABLE (ProjectId INT);
    IF @ProjectNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedProjects (ProjectId)
        SELECT DISTINCT ut.ProjectId
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@ProjectNames, ',') s
        WHERE ut.ProjectName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';

        IF NOT EXISTS (SELECT 1 FROM @SelectedProjects)
        BEGIN
            SELECT 0 AS TotalEngineers, 'No matching projects found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- TEAM FILTER
    -- =========================================
    DECLARE @SelectedTeams TABLE (TeamId INT);
    IF @TeamNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedTeams (TeamId)
        SELECT DISTINCT ut.TeamId
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@TeamNames, ',') s
        WHERE ut.TeamName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';

        IF NOT EXISTS (SELECT 1 FROM @SelectedTeams)
        BEGIN
            SELECT 0 AS TotalEngineers, 'No matching teams found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- REGION FILTER
    -- =========================================
    DECLARE @SelectedRegions TABLE (RegionId INT);
    IF @RegionNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedRegions (RegionId)
        SELECT DISTINCT sp.Id
        FROM dbo.StateProvince sp
        CROSS APPLY STRING_SPLIT(@RegionNames, ',') s
        WHERE sp.Name LIKE '%' + LTRIM(RTRIM(s.value)) + '%';

        IF NOT EXISTS (SELECT 1 FROM @SelectedRegions)
        BEGIN
            SELECT 0 AS TotalEngineers, 'No matching regions found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- EMPLOYEE NAME FILTER (partial match table)
    -- =========================================
    DECLARE @SelectedEmployees TABLE (EmployeeId INT);
    IF @EmployeeNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedEmployees (EmployeeId)
        SELECT DISTINCT e.Id
        FROM dbo.Employees e
        CROSS APPLY STRING_SPLIT(@EmployeeNames, ',') s
        WHERE (e.FirstName + ' ' + ISNULL(e.LastName, '')) LIKE '%' + LTRIM(RTRIM(s.value)) + '%'
          AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0;

        IF NOT EXISTS (SELECT 1 FROM @SelectedEmployees)
        BEGIN
            SELECT 0 AS TotalEngineers, 'No matching engineers found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- ROLE FILTER (filter employees by their role in TeamRoles)
    -- Default: only Field Engineer (2) and Resident Engineer (8)
    -- Pass "All" to skip role filtering
    -- =========================================
    DECLARE @SelectedRoles TABLE (RoleId INT);
    DECLARE @FilterByRole BIT = 1;

    IF LTRIM(RTRIM(ISNULL(@RoleNames, ''))) = 'All'
    BEGIN
        SET @FilterByRole = 0;  -- No role filter — show all employees
    END
    ELSE IF @RoleNames IS NULL
    BEGIN
        -- Default: only field-level roles (Field Engineer=2, Resident Engineer=8)
        INSERT INTO @SelectedRoles (RoleId) VALUES (2), (8);
        SET @FilterByRole = 1;
    END
    ELSE
    BEGIN
        -- User/agent specified specific roles
        INSERT INTO @SelectedRoles (RoleId)
        SELECT DISTINCT r.Id
        FROM dbo.Roles r
        CROSS APPLY STRING_SPLIT(@RoleNames, ',') s
        WHERE r.Name LIKE '%' + LTRIM(RTRIM(s.value)) + '%'
          AND r.IsActive = 1;

        -- If no matching roles found, fall back to no filter
        IF NOT EXISTS (SELECT 1 FROM @SelectedRoles)
            SET @FilterByRole = 0;
    END

    -- Build filtered employee IDs by role (only employees who hold the selected role in at least one team)
    DECLARE @RoleFilteredEmployees TABLE (EmployeeId INT);
    IF @FilterByRole = 1
    BEGIN
        INSERT INTO @RoleFilteredEmployees (EmployeeId)
        SELECT DISTINCT u.EmployeeId
        FROM dbo.TeamRoleUsers tru
        INNER JOIN dbo.TeamRoles tr ON tr.Id = tru.TeamRoleId
        INNER JOIN dbo.Users u ON u.Id = tru.UserId
        WHERE tr.RoleId IN (SELECT RoleId FROM @SelectedRoles)
          AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
          AND tr.IsActive = 1 AND ISNULL(tr.IsDeleted, 0) = 0
          AND u.EmployeeId IS NOT NULL;
    END

    -- =========================================
    -- DATE FILTER LOGIC
    -- =========================================
    DECLARE @FilterDateFrom DATE, @FilterDateTo DATE;

    IF @DateFrom IS NOT NULL
        SET @FilterDateFrom = @DateFrom;
    ELSE IF @Month IS NOT NULL AND @Year IS NOT NULL
        SET @FilterDateFrom = DATEFROMPARTS(@Year, @Month, 1);
    ELSE IF @Year IS NOT NULL
        SET @FilterDateFrom = DATEFROMPARTS(@Year, 1, 1);

    IF @DateTo IS NOT NULL
        SET @FilterDateTo = @DateTo;
    ELSE IF @Month IS NOT NULL AND @Year IS NOT NULL
        SET @FilterDateTo = EOMONTH(DATEFROMPARTS(@Year, @Month, 1));
    ELSE IF @Year IS NOT NULL
        SET @FilterDateTo = DATEFROMPARTS(@Year, 12, 31);

    -- =========================================
    -- RESULT SET 1: ENGINEER ROWS
    -- =========================================
    SELECT
        e.Id AS EmployeeId,
        LTRIM(RTRIM(e.FirstName + ' ' + ISNULL(e.LastName, ''))) AS EngineerName,
        e.EmpId AS EmployeeCode,
        tm.Name AS TeamName,
        p.Name AS ProjectName,
        sp.Name AS RegionName,
        COUNT(tk.Id) AS TotalTickets,
        SUM(CASE WHEN lc.Name = 'Closed' THEN 1 ELSE 0 END) AS CompletedTickets,
        SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS OpenTickets,
        SUM(CASE WHEN lc.Name = 'Suspended' THEN 1 ELSE 0 END) AS SuspendedTickets,
        SUM(CASE WHEN tk.SLAId IS NOT NULL AND lc.Name <> 'Closed'
                  AND GETDATE() > DATEADD(HOUR, ISNULL(slac.TargetHours, 0), tk.CreatedDate) THEN 1 ELSE 0 END) AS SLABreached,
        CASE WHEN COUNT(tk.Id) > 0
             THEN CAST(ROUND(100.0 * SUM(CASE WHEN lc.Name = 'Closed' THEN 1 ELSE 0 END) / COUNT(tk.Id), 2) AS DECIMAL(5,2))
             ELSE 0 END AS CompletionRate,
        SUM(CASE WHEN tt.Name = 'TR' THEN 1 ELSE 0 END) AS TRTickets,
        SUM(CASE WHEN tt.Name = 'PM' THEN 1 ELSE 0 END) AS PMTickets,
        SUM(CASE WHEN tt.Name = 'Other' OR tt.Name IS NULL THEN 1 ELSE 0 END) AS OtherTickets,
        -- Employee's primary role (highest priority across team assignments for this project)
        (SELECT TOP 1 r2.Name
         FROM dbo.TeamRoleUsers tru2
         INNER JOIN dbo.TeamRoles tr2 ON tr2.Id = tru2.TeamRoleId
         INNER JOIN dbo.Roles r2 ON r2.Id = tr2.RoleId
         INNER JOIN dbo.Users u2 ON u2.Id = tru2.UserId
         WHERE u2.EmployeeId = e.Id
           AND tru2.IsActive = 1
           AND tr2.IsActive = 1
           AND tr2.TeamId IN (SELECT Id FROM dbo.Teams WHERE ProjectId = p.Id)
         ORDER BY CASE r2.Id
             WHEN 1 THEN 1  -- Administrator
             WHEN 9 THEN 2  -- Operations Manager
             WHEN 6 THEN 3  -- Project Manager
             WHEN 7 THEN 4  -- Project Coordinator
             WHEN 4 THEN 5  -- Supervisor
             WHEN 5 THEN 6  -- Logistics Supervisor
             WHEN 8 THEN 7  -- Resident Engineer
             WHEN 2 THEN 8  -- Field Engineer
             ELSE 9 END
        ) AS RoleName
    FROM dbo.Tickets tk
    INNER JOIN dbo.Employees e ON e.Id = tk.EmployeeId
    INNER JOIN dbo.Teams tm ON tm.Id = tk.TeamId
    INNER JOIN dbo.Projects p ON p.Id = tk.ProjectId
    LEFT JOIN dbo.StateProvince sp ON sp.Id = tk.StateProvinceId
    LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
    LEFT JOIN dbo.LookupChild tt ON tt.Id = tk.TaskTypeId
    LEFT JOIN dbo.SLAConfig slac ON slac.Id = tk.SLAId
    WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
      AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0
      -- Access control
      AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
      -- Filters
      AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
      AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
      AND (@EmployeeNames IS NULL OR tk.EmployeeId IN (SELECT EmployeeId FROM @SelectedEmployees))
      -- Role filter (default: only field-level roles)
      AND (@FilterByRole = 0 OR tk.EmployeeId IN (SELECT EmployeeId FROM @RoleFilteredEmployees))
      -- Date filters (use ReportedDate — the user-facing ticket date)
      AND (@FilterDateFrom IS NULL OR CAST(tk.ReportedDate AS DATE) >= @FilterDateFrom)
      AND (@FilterDateTo IS NULL OR CAST(tk.ReportedDate AS DATE) <= @FilterDateTo)
    GROUP BY e.Id, e.FirstName, e.LastName, e.EmpId, tm.Name, p.Id, p.Name, sp.Name
    ORDER BY CompletedTickets DESC, TotalTickets DESC;

    -- =========================================
    -- RESULT SET 2: SUMMARY
    -- =========================================
    SELECT
        COUNT(DISTINCT tk.EmployeeId) AS TotalEngineers,
        COUNT(tk.Id) AS TotalTickets,
        SUM(CASE WHEN lc.Name = 'Closed' THEN 1 ELSE 0 END) AS TotalCompleted,
        SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS TotalOpen,
        SUM(CASE WHEN lc.Name = 'Suspended' THEN 1 ELSE 0 END) AS TotalSuspended,
        SUM(CASE WHEN tk.SLAId IS NOT NULL AND lc.Name <> 'Closed'
                  AND GETDATE() > DATEADD(HOUR, ISNULL(slac.TargetHours, 0), tk.CreatedDate) THEN 1 ELSE 0 END) AS TotalSLABreached,
        CASE WHEN COUNT(tk.Id) > 0
             THEN CAST(ROUND(100.0 * SUM(CASE WHEN lc.Name = 'Closed' THEN 1 ELSE 0 END) / COUNT(tk.Id), 2) AS DECIMAL(5,2))
             ELSE 0 END AS OverallCompletionRate,
        SUM(CASE WHEN tt.Name = 'TR' THEN 1 ELSE 0 END) AS TotalTR,
        SUM(CASE WHEN tt.Name = 'PM' THEN 1 ELSE 0 END) AS TotalPM,
        SUM(CASE WHEN tt.Name = 'Other' OR tt.Name IS NULL THEN 1 ELSE 0 END) AS TotalOther,
        COALESCE(@EmployeeNames, 'All Engineers') AS EmployeeFilter,
        COALESCE(@ProjectNames, 'All Projects') AS ProjectFilter,
        COALESCE(@TeamNames, 'All Teams') AS TeamFilter,
        COALESCE(@RegionNames, 'All Regions') AS RegionFilter,
        COALESCE(CONVERT(NVARCHAR, @FilterDateFrom, 23), 'No Start') AS DateFromFilter,
        COALESCE(CONVERT(NVARCHAR, @FilterDateTo, 23), 'No End') AS DateToFilter,
        'Success' AS Message
    FROM dbo.Tickets tk
    INNER JOIN dbo.Employees e ON e.Id = tk.EmployeeId
    INNER JOIN dbo.Teams tm ON tm.Id = tk.TeamId
    LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
    LEFT JOIN dbo.LookupChild tt ON tt.Id = tk.TaskTypeId
    LEFT JOIN dbo.SLAConfig slac ON slac.Id = tk.SLAId
    WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
      AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0
      AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
      AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
      AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
      AND (@EmployeeNames IS NULL OR tk.EmployeeId IN (SELECT EmployeeId FROM @SelectedEmployees))
      -- Role filter
      AND (@FilterByRole = 0 OR tk.EmployeeId IN (SELECT EmployeeId FROM @RoleFilteredEmployees))
      AND (@FilterDateFrom IS NULL OR CAST(tk.ReportedDate AS DATE) >= @FilterDateFrom)
      AND (@FilterDateTo IS NULL OR CAST(tk.ReportedDate AS DATE) <= @FilterDateTo);

    -- =========================================
    -- RESULT SET 3: ACTIVITY LOG (only if @IncludeActivity = 1)
    -- =========================================
    IF @IncludeActivity = 1
    BEGIN
        SELECT
            LTRIM(RTRIM(e.FirstName + ' ' + ISNULL(e.LastName, ''))) AS EngineerName,
            at_lc.Name AS ActivityType,
            dal.WorkingDate,
            dal.DurationHours,
            dal.DistanceTravelled,
            dal.OvertimeMinutes,
            ts_lc.Name AS TicketStatus,
            tm.Name AS TeamName
        FROM dbo.DailyActivityLog dal
        INNER JOIN dbo.Employees e ON e.Id = dal.EmployeeId
        INNER JOIN dbo.Teams tm ON tm.Id = dal.TeamId
        LEFT JOIN dbo.LookupChild at_lc ON at_lc.Id = dal.ActivityTypeId
        LEFT JOIN dbo.LookupChild ts_lc ON ts_lc.Id = dal.TicketStatusId
        WHERE dal.IsActive = 1 AND ISNULL(dal.IsDeleted, 0) = 0
          AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0
          -- Access control
          AND (@CanViewAll = 1 OR dal.TeamId IN (SELECT TeamId FROM @UserTeams))
          -- Filters
          AND (@ProjectNames IS NULL OR dal.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
          AND (@TeamNames IS NULL OR dal.TeamId IN (SELECT TeamId FROM @SelectedTeams))
          AND (@EmployeeNames IS NULL OR dal.EmployeeId IN (SELECT EmployeeId FROM @SelectedEmployees))
          -- Role filter
          AND (@FilterByRole = 0 OR dal.EmployeeId IN (SELECT EmployeeId FROM @RoleFilteredEmployees))
          -- Date filters on WorkingDate
          AND (@FilterDateFrom IS NULL OR dal.WorkingDate >= @FilterDateFrom)
          AND (@FilterDateTo IS NULL OR dal.WorkingDate <= @FilterDateTo)
        ORDER BY dal.WorkingDate DESC, e.FirstName;
    END
END
GO
