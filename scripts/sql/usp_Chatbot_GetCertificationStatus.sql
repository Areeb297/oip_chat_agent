USE [TickTraq]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER PROCEDURE [dbo].[usp_Chatbot_GetCertificationStatus]
(
    @Username NVARCHAR(100),
    @ProjectNames NVARCHAR(MAX) = NULL,        -- Comma-separated project names
    @EmployeeNames NVARCHAR(MAX) = NULL,       -- Comma-separated, partial match on FirstName + LastName
    @ExpiringWithinDays INT = 90,              -- Show certs expiring within N days
    @ShowAll BIT = 0                           -- 0 = only expiring/expired, 1 = all certs
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
    -- EMPLOYEE NAME FILTER
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
    -- RESULT SET 1: CERTIFICATION DETAILS
    -- Joins CertificationEmployee with Employees and Projects
    -- =========================================
    SELECT
        LTRIM(RTRIM(e.FirstName + ' ' + ISNULL(e.LastName, ''))) AS EngineerName,
        e.EmpId AS EmployeeCode,
        ce.Name AS CertificationName,
        ce.StartDate,
        ce.EndDate,
        ce.ExpiryDate,
        CASE
            WHEN ce.ExpiryDate IS NULL THEN 'No Expiry Set'
            WHEN ce.ExpiryDate < GETDATE() THEN 'Expired'
            WHEN DATEDIFF(DAY, GETDATE(), ce.ExpiryDate) <= @ExpiringWithinDays THEN 'Expiring Soon'
            ELSE 'Valid'
        END AS Status,
        CASE
            WHEN ce.ExpiryDate IS NULL THEN NULL
            ELSE DATEDIFF(DAY, GETDATE(), ce.ExpiryDate)
        END AS DaysUntilExpiry,
        p.Name AS ProjectName,
        -- Try to find team via TeamRoleUsers
        (SELECT TOP 1 tm.Name FROM dbo.TeamRoleUsers tru2
         INNER JOIN dbo.TeamRoles tr2 ON tr2.Id = tru2.TeamRoleId
         INNER JOIN dbo.Teams tm ON tm.Id = tr2.TeamId
         INNER JOIN dbo.Users u2 ON u2.Id = tru2.UserId
         WHERE u2.EmployeeId = e.Id AND tru2.IsActive = 1 AND ISNULL(tru2.IsDeleted, 0) = 0
        ) AS TeamName
    FROM dbo.CertificationEmployee ce
    INNER JOIN dbo.Employees e ON e.Id = ce.EmployeeId
    LEFT JOIN dbo.Projects p ON p.Id = ce.ProjectId
    WHERE ce.IsActive = 1 AND ISNULL(ce.IsDeleted, 0) = 0
      AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0
      -- Access control
      AND (@CanViewAll = 1
           OR ce.ProjectId IN (SELECT ProjectId FROM @UserTeams)
           OR ce.EmployeeId = @EmployeeId)
      -- Project filter
      AND (@ProjectNames IS NULL OR ce.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      -- Employee filter
      AND (@EmployeeNames IS NULL OR ce.EmployeeId IN (SELECT EmployeeId FROM @SelectedEmployees))
      -- Show all or only expiring/expired
      AND (@ShowAll = 1
           OR ce.ExpiryDate IS NULL
           OR ce.ExpiryDate < GETDATE()
           OR DATEDIFF(DAY, GETDATE(), ce.ExpiryDate) <= @ExpiringWithinDays)
    ORDER BY
        CASE
            WHEN ce.ExpiryDate IS NULL THEN 3
            WHEN ce.ExpiryDate < GETDATE() THEN 1
            WHEN DATEDIFF(DAY, GETDATE(), ce.ExpiryDate) <= @ExpiringWithinDays THEN 2
            ELSE 4
        END,
        ce.ExpiryDate ASC;

    -- =========================================
    -- RESULT SET 2: SUMMARY
    -- =========================================
    SELECT
        COUNT(DISTINCT ce.EmployeeId) AS TotalEngineers,
        COUNT(ce.Id) AS TotalCertifications,
        SUM(CASE WHEN ce.ExpiryDate IS NOT NULL AND ce.ExpiryDate >= GETDATE()
                  AND DATEDIFF(DAY, GETDATE(), ce.ExpiryDate) > @ExpiringWithinDays THEN 1 ELSE 0 END) AS ValidCerts,
        SUM(CASE WHEN ce.ExpiryDate IS NOT NULL AND ce.ExpiryDate < GETDATE() THEN 1 ELSE 0 END) AS ExpiredCerts,
        SUM(CASE WHEN ce.ExpiryDate IS NOT NULL
                  AND ce.ExpiryDate >= GETDATE()
                  AND DATEDIFF(DAY, GETDATE(), ce.ExpiryDate) <= @ExpiringWithinDays THEN 1 ELSE 0 END) AS ExpiringSoonCerts,
        SUM(CASE WHEN ce.ExpiryDate IS NULL THEN 1 ELSE 0 END) AS NoExpiryCerts,
        COALESCE(@EmployeeNames, 'All Engineers') AS EmployeeFilter,
        COALESCE(@ProjectNames, 'All Projects') AS ProjectFilter,
        @ExpiringWithinDays AS ExpiringWithinDays,
        'Success' AS Message
    FROM dbo.CertificationEmployee ce
    INNER JOIN dbo.Employees e ON e.Id = ce.EmployeeId
    WHERE ce.IsActive = 1 AND ISNULL(ce.IsDeleted, 0) = 0
      AND e.IsActive = 1 AND ISNULL(e.IsDeleted, 0) = 0
      AND (@CanViewAll = 1
           OR ce.ProjectId IN (SELECT ProjectId FROM @UserTeams)
           OR ce.EmployeeId = @EmployeeId)
      AND (@ProjectNames IS NULL OR ce.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@EmployeeNames IS NULL OR ce.EmployeeId IN (SELECT EmployeeId FROM @SelectedEmployees));
END
GO
