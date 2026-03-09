USE [TickTraq]
GO
/****** Object:  StoredProcedure [dbo].[usp_Chatbot_GetLookups]    Script Date: 09/03/2026 11:11:05 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
ALTER PROCEDURE [dbo].[usp_Chatbot_GetLookups]
    @LookupType NVARCHAR(50) = NULL,  -- 'Regions', 'Projects', 'Teams', 'Statuses', 'All'
    @Username NVARCHAR(100) = NULL    -- Optional: filter by user's accessible data
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Get UserId if username provided (for filtered lookups)
    DECLARE @UserId INT = NULL;
    IF @Username IS NOT NULL
    BEGIN
        SELECT @UserId = Id FROM Users WHERE Username = @Username AND ISNULL(IsDeleted, 0) = 0;
    END
    
    -- =========================================
    -- Regions (from StateProvince table)
    -- =========================================
    IF @LookupType IS NULL OR @LookupType = 'All' OR @LookupType = 'Regions'
    BEGIN
        IF @UserId IS NOT NULL
        BEGIN
            -- Return only regions the user has access to (via their teams)
            SELECT DISTINCT 
                sp.Id AS RegionId,
                sp.Name AS RegionName,
                sp.Code AS RegionCode
            FROM dbo.StateProvince sp
            INNER JOIN dbo.Teams t ON t.RegionId = sp.Id
            INNER JOIN dbo.TeamRoles tr ON tr.TeamId = t.Id
            INNER JOIN dbo.TeamRoleUsers tru ON tru.TeamRoleId = tr.Id
            WHERE tru.UserId = @UserId
              AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
              AND t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            ORDER BY sp.Name;
        END
        ELSE
        BEGIN
            -- Return all regions (no IsDeleted on StateProvince)
            SELECT 
                Id AS RegionId,
                Name AS RegionName,
                Code AS RegionCode
            FROM dbo.StateProvince
            ORDER BY Name;
        END
    END
    
    -- =========================================
    -- Projects
    -- =========================================
    IF @LookupType IS NULL OR @LookupType = 'All' OR @LookupType = 'Projects'
    BEGIN
        IF @UserId IS NOT NULL
        BEGIN
            -- Return only projects the user has access to
            SELECT DISTINCT 
                p.Id AS ProjectId,
                p.Name AS ProjectName
            FROM dbo.Projects p
            INNER JOIN dbo.Teams t ON t.ProjectId = p.Id
            INNER JOIN dbo.TeamRoles tr ON tr.TeamId = t.Id
            INNER JOIN dbo.TeamRoleUsers tru ON tru.TeamRoleId = tr.Id
            WHERE tru.UserId = @UserId
              AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
              AND p.IsActive = 1 AND ISNULL(p.IsDeleted, 0) = 0
            ORDER BY p.Name;
        END
        ELSE
        BEGIN
            -- Return all active projects
            SELECT 
                Id AS ProjectId,
                Name AS ProjectName
            FROM dbo.Projects
            WHERE IsActive = 1 AND ISNULL(IsDeleted, 0) = 0
            ORDER BY Name;
        END
    END
    
    -- =========================================
    -- Teams
    -- =========================================
    IF @LookupType IS NULL OR @LookupType = 'All' OR @LookupType = 'Teams'
    BEGIN
        IF @UserId IS NOT NULL
        BEGIN
            -- Return only teams the user belongs to
            SELECT DISTINCT 
                t.Id AS TeamId,
                t.Name AS TeamName,
                p.Name AS ProjectName,
                sp.Name AS RegionName
            FROM dbo.Teams t
            INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
            LEFT JOIN dbo.StateProvince sp ON sp.Id = t.RegionId
            INNER JOIN dbo.TeamRoles tr ON tr.TeamId = t.Id
            INNER JOIN dbo.TeamRoleUsers tru ON tru.TeamRoleId = tr.Id
            WHERE tru.UserId = @UserId
              AND tru.IsActive = 1 AND ISNULL(tru.IsDeleted, 0) = 0
              AND t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            ORDER BY t.Name;
        END
        ELSE
        BEGIN
            -- Return all active teams
            SELECT 
                t.Id AS TeamId,
                t.Name AS TeamName,
                p.Name AS ProjectName,
                sp.Name AS RegionName
            FROM dbo.Teams t
            INNER JOIN dbo.Projects p ON p.Id = t.ProjectId
            LEFT JOIN dbo.StateProvince sp ON sp.Id = t.RegionId
            WHERE t.IsActive = 1 AND ISNULL(t.IsDeleted, 0) = 0
            ORDER BY t.Name;
        END
    END
    
    -- =========================================
    -- Ticket Statuses (from LookupChild using LookupMasterId)
    -- =========================================
    IF @LookupType IS NULL OR @LookupType = 'All' OR @LookupType = 'Statuses'
    BEGIN
        SELECT 
            lc.Id AS StatusId,
            lc.Code AS StatusCode,
            lc.Name AS StatusName,
            lc.Color AS StatusColor,
            lc.Sequence
        FROM dbo.LookupChild lc
        INNER JOIN dbo.LookupMaster lm ON lm.Id = lc.LookupMasterId
        WHERE lm.Name = 'CallStatus'  -- or whatever the master name is
          AND lc.IsActive = 1 
          AND ISNULL(lc.IsDeleted, 0) = 0
        ORDER BY lc.Sequence, lc.Id;
    END

    -- =========================================
    -- Task Types (from LookupChild where LookupMaster = 'Task Type')
    -- =========================================
    IF @LookupType IS NULL OR @LookupType = 'All' OR @LookupType = 'TaskTypes'
    BEGIN
        SELECT
            lc.Id AS TaskTypeId,
            lc.Name AS TaskTypeName
        FROM dbo.LookupChild lc
        INNER JOIN dbo.LookupMaster lm ON lm.Id = lc.LookupMasterId
        WHERE lm.Name = 'Task Type'
          AND lc.IsActive = 1
          AND ISNULL(lc.IsDeleted, 0) = 0
        ORDER BY lc.Id;
    END
END