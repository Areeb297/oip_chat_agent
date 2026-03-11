USE [TickTraq]
GO
/****** Object:  StoredProcedure [dbo].[usp_Chatbot_GetTicketSummary]    Script Date: 09/03/2026 11:09:31 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

ALTER PROCEDURE [dbo].[usp_Chatbot_GetTicketSummary]
(
    @Username NVARCHAR(100),
    @ProjectNames NVARCHAR(MAX) = NULL,
    @TeamNames NVARCHAR(MAX) = NULL,
    @RegionNames NVARCHAR(MAX) = NULL,
    @Month INT = NULL,
    @Year INT = NULL,
    @DateFrom DATE = NULL,
    @DateTo DATE = NULL,
    @IncludeBreakdown BIT = 0,
    @TaskTypeNames NVARCHAR(MAX) = NULL    -- NEW: "PM", "TR", "Other", or "PM,TR"
)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Handle month/year defaults
    IF @Month IS NOT NULL AND @Year IS NULL
        SET @Year = YEAR(GETDATE());
    
    -- Get user
    DECLARE @UserId INT, @EmployeeId INT;
    
    SELECT @UserId = Id, @EmployeeId = EmployeeId
    FROM Users 
    WHERE Username = @Username AND ISNULL(IsDeleted, 0) = 0;
    
    IF @UserId IS NULL
    BEGIN
        SELECT 0 AS TotalTickets, 'User not found' AS Message;
        RETURN;
    END
    
    -- Get user's teams (includes RegionId from Teams table)
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
    
    -- Parse comma-separated project names
    DECLARE @SelectedProjects TABLE (ProjectId INT, ProjectName NVARCHAR(200));
    IF @ProjectNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedProjects (ProjectId, ProjectName)
        SELECT DISTINCT ut.ProjectId, ut.ProjectName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@ProjectNames, ',') s
        WHERE ut.ProjectName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END
    
    -- Parse comma-separated team names
    DECLARE @SelectedTeams TABLE (TeamId INT, TeamName NVARCHAR(200));
    IF @TeamNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedTeams (TeamId, TeamName)
        SELECT DISTINCT ut.TeamId, ut.TeamName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@TeamNames, ',') s
        WHERE ut.TeamName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END
    
    -- Parse comma-separated region names
    DECLARE @SelectedRegions TABLE (RegionId INT, RegionName NVARCHAR(200));
    IF @RegionNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedRegions (RegionId, RegionName)
        SELECT DISTINCT ut.RegionId, ut.RegionName
        FROM @UserTeams ut
        CROSS APPLY STRING_SPLIT(@RegionNames, ',') s
        WHERE ut.RegionName LIKE '%' + LTRIM(RTRIM(s.value)) + '%';
    END
    
    -- Parse comma-separated task type names
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

    -- Validation checks
    IF @TeamNames IS NOT NULL AND NOT EXISTS (SELECT 1 FROM @SelectedTeams)
    BEGIN
        SELECT 0 AS TotalTickets, 0 AS OpenTickets, 0 AS SuspendedTickets,
               0 AS CompletedTickets, 0 AS PendingApproval, 0 AS SLABreached,
               0.00 AS CompletionRate, @Username AS Username, '' AS UserRole,
               @ProjectNames AS ProjectFilter, @TeamNames AS TeamFilter,
               @RegionNames AS RegionFilter, @Month AS MonthFilter, @Year AS YearFilter,
               'No matching teams found' AS Message;
        RETURN;
    END
    
    IF @ProjectNames IS NOT NULL AND NOT EXISTS (SELECT 1 FROM @SelectedProjects)
    BEGIN
        SELECT 0 AS TotalTickets, 0 AS OpenTickets, 0 AS SuspendedTickets,
               0 AS CompletedTickets, 0 AS PendingApproval, 0 AS SLABreached,
               0.00 AS CompletionRate, @Username AS Username, '' AS UserRole,
               @ProjectNames AS ProjectFilter, @TeamNames AS TeamFilter,
               @RegionNames AS RegionFilter, @Month AS MonthFilter, @Year AS YearFilter,
               'No matching projects found' AS Message;
        RETURN;
    END
    
    IF @RegionNames IS NOT NULL AND NOT EXISTS (SELECT 1 FROM @SelectedRegions)
    BEGIN
        SELECT 0 AS TotalTickets, 0 AS OpenTickets, 0 AS SuspendedTickets,
               0 AS CompletedTickets, 0 AS PendingApproval, 0 AS SLABreached,
               0.00 AS CompletionRate, @Username AS Username, '' AS UserRole,
               @ProjectNames AS ProjectFilter, @TeamNames AS TeamFilter,
               @RegionNames AS RegionFilter, @Month AS MonthFilter, @Year AS YearFilter,
               'No matching regions found' AS Message;
        RETURN;
    END

    IF @TaskTypeNames IS NOT NULL AND NOT EXISTS (SELECT 1 FROM @SelectedTaskTypes)
    BEGIN
        SELECT 0 AS TotalTickets, 0 AS OpenTickets, 0 AS SuspendedTickets,
               0 AS CompletedTickets, 0 AS PendingApproval, 0 AS SLABreached,
               0.00 AS CompletionRate, @Username AS Username, '' AS UserRole,
               @ProjectNames AS ProjectFilter, @TeamNames AS TeamFilter,
               @RegionNames AS RegionFilter, @Month AS MonthFilter, @Year AS YearFilter,
               'No matching task types found' AS Message;
        RETURN;
    END

    -- Check roles
    DECLARE @CanViewAll BIT = CASE WHEN EXISTS (SELECT 1 FROM @UserTeams WHERE RoleId IN (1,6,7)) THEN 1 ELSE 0 END;
    DECLARE @IsSupervisor BIT = CASE WHEN EXISTS (SELECT 1 FROM @UserTeams WHERE RoleId = 4) THEN 1 ELSE 0 END;
    
    -- Build filtered teams list based on all criteria
    DECLARE @FilteredTeams TABLE (TeamId INT);
    
    INSERT INTO @FilteredTeams (TeamId)
    SELECT DISTINCT TeamId
    FROM @UserTeams ut
    WHERE 
        (@TeamNames IS NULL OR ut.TeamId IN (SELECT TeamId FROM @SelectedTeams))
        AND (@ProjectNames IS NULL OR ut.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
        AND (@RegionNames IS NULL OR ut.RegionId IN (SELECT RegionId FROM @SelectedRegions));
    
    -- =========================================
    -- RESULT SET 1: Summary
    -- =========================================
    SELECT 
        COUNT(*) AS TotalTickets,
        SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS OpenTickets,
        SUM(CASE WHEN t.CallStatusId = 9 THEN 1 ELSE 0 END) AS SuspendedTickets,
        SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1 ELSE 0 END) AS CompletedTickets,
        SUM(CASE WHEN t.ApprovalStatusId = 15 AND t.CallStatusId = 18 THEN 1 ELSE 0 END) AS PendingApproval,  -- ✅ FIXED: Added CallStatusId = 18
        SUM(CASE
            WHEN t.SLAId IS NOT NULL
             AND t.CallStatusId != 9
             AND ISNULL(lc.Name,'') NOT IN ('Completed', 'Closed')
             AND DATEDIFF(DAY, t.CreatedAt, GETDATE()) > 1
            THEN 1 ELSE 0
        END) AS SLABreached,
        CAST(
            CASE WHEN COUNT(*) > 0 
                THEN (SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1.0 ELSE 0 END) / COUNT(*)) * 100
                ELSE 0 
            END AS DECIMAL(5,2)
        ) AS CompletionRate,
        @Username AS Username,
        CASE WHEN @CanViewAll = 1 THEN 'Admin/PM/PC' 
             WHEN @IsSupervisor = 1 THEN 'Supervisor'
             ELSE 'Engineer' END AS UserRole,
        COALESCE(@ProjectNames, 'All Projects') AS ProjectFilter,
        COALESCE(@TeamNames, 'All Teams') AS TeamFilter,
        COALESCE(@RegionNames, 'All Regions') AS RegionFilter,
        @Month AS MonthFilter,
        @Year AS YearFilter,
        'Success' AS Message
    FROM dbo.Tickets t
    LEFT JOIN dbo.LookupChild lc ON lc.Id = t.CallStatusId
    WHERE 
        t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
        AND t.TeamId IN (SELECT TeamId FROM @FilteredTeams)
        AND (@ProjectNames IS NULL OR t.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))  -- ✅ FIXED: Added ProjectId filter
        AND (
            (@Month IS NOT NULL AND MONTH(t.CreatedAt) = @Month AND YEAR(t.CreatedAt) = @Year)
            OR
            (@DateFrom IS NOT NULL AND CAST(t.CreatedAt AS DATE) >= @DateFrom 
             AND CAST(t.CreatedAt AS DATE) <= ISNULL(@DateTo, GETDATE()))
            OR
            (@Month IS NULL AND @DateFrom IS NULL)
        )
        AND (@TaskTypeNames IS NULL OR t.TaskTypeId IN (SELECT TaskTypeId FROM @SelectedTaskTypes))
        AND (@CanViewAll = 1 OR t.EmployeeId = @EmployeeId OR (@IsSupervisor = 1 AND t.CallStatusId = 9));

    -- =========================================
    -- BREAKDOWNS (if requested)
    -- =========================================
    IF @IncludeBreakdown = 1
    BEGIN
        -- RESULT SET 2: Breakdown by Region
        SELECT 
            sp.Name AS RegionName,
            COUNT(*) AS TotalTickets,
            SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS OpenTickets,
            SUM(CASE WHEN t.CallStatusId = 9 THEN 1 ELSE 0 END) AS SuspendedTickets,
            SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1 ELSE 0 END) AS CompletedTickets,
            SUM(CASE WHEN t.ApprovalStatusId = 15 AND t.CallStatusId = 18 THEN 1 ELSE 0 END) AS PendingApproval,  -- ✅ FIXED
            SUM(CASE 
                WHEN t.CallStatusId != 9 
                 AND ISNULL(lc.Name,'') NOT IN ('Completed', 'Closed')
                 AND DATEDIFF(DAY, t.CreatedAt, GETDATE()) > 1 
                THEN 1 ELSE 0 
            END) AS SLABreached,
            CAST(
                CASE WHEN COUNT(*) > 0 
                    THEN (SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1.0 ELSE 0 END) / COUNT(*)) * 100
                    ELSE 0 
                END AS DECIMAL(5,2)
            ) AS CompletionRate
        FROM dbo.Tickets t
        LEFT JOIN dbo.LookupChild lc ON lc.Id = t.CallStatusId
        INNER JOIN dbo.Teams tm ON tm.Id = t.TeamId
        LEFT JOIN dbo.StateProvince sp ON sp.Id = tm.RegionId
        WHERE 
            t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            AND t.TeamId IN (SELECT TeamId FROM @FilteredTeams)
            AND (@ProjectNames IS NULL OR t.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))  -- ✅ FIXED
            AND (
                (@Month IS NOT NULL AND MONTH(t.CreatedAt) = @Month AND YEAR(t.CreatedAt) = @Year)
                OR (@DateFrom IS NOT NULL AND CAST(t.CreatedAt AS DATE) >= @DateFrom 
                    AND CAST(t.CreatedAt AS DATE) <= ISNULL(@DateTo, GETDATE()))
                OR (@Month IS NULL AND @DateFrom IS NULL)
            )
            AND (@TaskTypeNames IS NULL OR t.TaskTypeId IN (SELECT TaskTypeId FROM @SelectedTaskTypes))
            AND (@CanViewAll = 1 OR t.EmployeeId = @EmployeeId OR (@IsSupervisor = 1 AND t.CallStatusId = 9))
        GROUP BY sp.Name
        ORDER BY TotalTickets DESC;
        
        -- RESULT SET 3: Breakdown by Project
        SELECT 
            p.Name AS ProjectName,
            COUNT(*) AS TotalTickets,
            SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS OpenTickets,
            SUM(CASE WHEN t.CallStatusId = 9 THEN 1 ELSE 0 END) AS SuspendedTickets,
            SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1 ELSE 0 END) AS CompletedTickets,
            SUM(CASE WHEN t.ApprovalStatusId = 15 AND t.CallStatusId = 18 THEN 1 ELSE 0 END) AS PendingApproval,  -- ✅ FIXED
            SUM(CASE 
                WHEN t.CallStatusId != 9 
                 AND ISNULL(lc.Name,'') NOT IN ('Completed', 'Closed')
                 AND DATEDIFF(DAY, t.CreatedAt, GETDATE()) > 1 
                THEN 1 ELSE 0 
            END) AS SLABreached,
            CAST(
                CASE WHEN COUNT(*) > 0 
                    THEN (SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1.0 ELSE 0 END) / COUNT(*)) * 100
                    ELSE 0 
                END AS DECIMAL(5,2)
            ) AS CompletionRate
        FROM dbo.Tickets t
        LEFT JOIN dbo.LookupChild lc ON lc.Id = t.CallStatusId
        INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
        WHERE 
            t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            AND t.TeamId IN (SELECT TeamId FROM @FilteredTeams)
            AND (@ProjectNames IS NULL OR t.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))  -- ✅ FIXED
            AND (
                (@Month IS NOT NULL AND MONTH(t.CreatedAt) = @Month AND YEAR(t.CreatedAt) = @Year)
                OR (@DateFrom IS NOT NULL AND CAST(t.CreatedAt AS DATE) >= @DateFrom 
                    AND CAST(t.CreatedAt AS DATE) <= ISNULL(@DateTo, GETDATE()))
                OR (@Month IS NULL AND @DateFrom IS NULL)
            )
            AND (@TaskTypeNames IS NULL OR t.TaskTypeId IN (SELECT TaskTypeId FROM @SelectedTaskTypes))
            AND (@CanViewAll = 1 OR t.EmployeeId = @EmployeeId OR (@IsSupervisor = 1 AND t.CallStatusId = 9))
        GROUP BY p.Name
        ORDER BY TotalTickets DESC;
        
        -- RESULT SET 4: Breakdown by Team
        SELECT 
            tm.Name AS TeamName,
            sp.Name AS RegionName,
            p.Name AS ProjectName,
            COUNT(*) AS TotalTickets,
            SUM(CASE WHEN lc.Name = 'Open' THEN 1 ELSE 0 END) AS OpenTickets,
            SUM(CASE WHEN lc.Name IN ('Completed', 'Closed') THEN 1 ELSE 0 END) AS CompletedTickets,
            SUM(CASE WHEN t.ApprovalStatusId = 15 AND t.CallStatusId = 18 THEN 1 ELSE 0 END) AS PendingApproval,  -- ✅ FIXED
            SUM(CASE 
                WHEN t.CallStatusId != 9 
                 AND ISNULL(lc.Name,'') NOT IN ('Completed', 'Closed')
                 AND DATEDIFF(DAY, t.CreatedAt, GETDATE()) > 1 
                THEN 1 ELSE 0 
            END) AS SLABreached
        FROM dbo.Tickets t
        LEFT JOIN dbo.LookupChild lc ON lc.Id = t.CallStatusId
        INNER JOIN dbo.Teams tm ON tm.Id = t.TeamId
        INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
        LEFT JOIN dbo.StateProvince sp ON sp.Id = tm.RegionId
        WHERE 
            t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            AND t.TeamId IN (SELECT TeamId FROM @FilteredTeams)
            AND (@ProjectNames IS NULL OR t.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))  -- ✅ FIXED
            AND (
                (@Month IS NOT NULL AND MONTH(t.CreatedAt) = @Month AND YEAR(t.CreatedAt) = @Year)
                OR (@DateFrom IS NOT NULL AND CAST(t.CreatedAt AS DATE) >= @DateFrom 
                    AND CAST(t.CreatedAt AS DATE) <= ISNULL(@DateTo, GETDATE()))
                OR (@Month IS NULL AND @DateFrom IS NULL)
            )
            AND (@TaskTypeNames IS NULL OR t.TaskTypeId IN (SELECT TaskTypeId FROM @SelectedTaskTypes))
            AND (@CanViewAll = 1 OR t.EmployeeId = @EmployeeId OR (@IsSupervisor = 1 AND t.CallStatusId = 9))
        GROUP BY tm.Name, sp.Name, p.Name
        ORDER BY TotalTickets DESC;
    END
END