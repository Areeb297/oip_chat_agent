USE [TickTraq]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER PROCEDURE [dbo].[usp_Chatbot_GetPMChecklistData]
(
    @Username NVARCHAR(100),
    @SiteName NVARCHAR(200) = NULL,            -- Filter by site (partial match: '730' matches 'A730')
    @FieldName NVARCHAR(200) = NULL,           -- Extension field: 'Panel IP', 'NVR IP', 'Keypad Model', etc.
    @FieldValue NVARCHAR(500) = NULL,          -- Search by value in Comments: 'D1255B', '173.31.1.244'
    @SubCategoryName NVARCHAR(200) = NULL,     -- Equipment name: 'Door Contact', 'Motion Detector', etc.
    @PMCode NVARCHAR(100) = NULL,              -- Filter by PM code
    @TicketStatus NVARCHAR(50) = NULL,         -- 'Open', 'Closed'
    @CategoryName NVARCHAR(200) = NULL,        -- 'CCTV System', 'Intrusion Alarm System', etc.
    @ProjectNames NVARCHAR(MAX) = NULL,        -- Comma-separated project names
    @TeamNames NVARCHAR(MAX) = NULL,           -- Comma-separated team names (e.g. 'Central,Western')
    @RegionNames NVARCHAR(MAX) = NULL,         -- Comma-separated region/state names (e.g. 'Riyadh,Makkah')
    @CityNames NVARCHAR(MAX) = NULL,           -- Comma-separated city names (e.g. 'Jeddah,Medina')
    @DateFrom DATE = NULL,                     -- Start date filter on ChecklistDate
    @DateTo DATE = NULL,                       -- End date filter on ChecklistDate
    @LatestOnly BIT = 1                        -- 1 = latest PM visit per site only, 0 = all visits
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
        SELECT 0 AS TotalResults, 'User not found' AS Message;
        RETURN;
    END

    -- =========================================
    -- ROLE-BASED ACCESS (same pattern as GetTicketSummary)
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
    -- PROJECT FILTER (comma-separated, partial match)
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
            SELECT 0 AS TotalResults, 'No matching projects found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- TEAM FILTER (comma-separated, partial match)
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
            SELECT 0 AS TotalResults, 'No matching teams found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- REGION FILTER (StateProvince, comma-separated, partial match)
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
            SELECT 0 AS TotalResults, 'No matching regions found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- CITY FILTER (comma-separated, partial match)
    -- =========================================
    DECLARE @SelectedCities TABLE (CityId INT);
    IF @CityNames IS NOT NULL
    BEGIN
        INSERT INTO @SelectedCities (CityId)
        SELECT DISTINCT ci.Id
        FROM dbo.City ci
        CROSS APPLY STRING_SPLIT(@CityNames, ',') s
        WHERE ci.Name LIKE '%' + LTRIM(RTRIM(s.value)) + '%';

        IF NOT EXISTS (SELECT 1 FROM @SelectedCities)
        BEGIN
            SELECT 0 AS TotalResults, 'No matching cities found' AS Message;
            RETURN;
        END
    END

    -- =========================================
    -- MODE 1: EXTENSION DATA (Panel IP, NVR IP, Models, Serial #s, MAC addresses)
    -- Triggered when @FieldName is provided, or @FieldValue is provided
    -- =========================================
    IF @FieldName IS NOT NULL OR @FieldValue IS NOT NULL
    BEGIN
        ;WITH RankedExtensions AS (
            SELECT
                tk.SiteName,
                tk.Id AS TicketId,
                ce.Name AS FieldName,
                pci.Comments AS FieldValue,
                c.CategoryName,
                pc.PMcode,
                pc.OperatorName,
                pc.ChecklistDate,
                lc.Name AS TicketStatus,
                ROW_NUMBER() OVER (
                    PARTITION BY tk.SiteName, ce.Name
                    ORDER BY pc.ChecklistDate DESC, pc.Id DESC
                ) AS RowNum
            FROM dbo.Tickets tk
            INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
            INNER JOIN dbo.PMChecklistItems pci ON pci.PMChecklistId = pc.Id
            INNER JOIN dbo.CategoryExtension ce ON ce.Id = pci.CategoryExtensionId
            INNER JOIN dbo.Category c ON c.Id = pci.CategoryId
            LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
            WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
              AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
              AND pci.Comments IS NOT NULL AND LEN(LTRIM(RTRIM(pci.Comments))) > 0
              AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
              AND (@FieldName IS NULL OR ce.Name LIKE '%' + @FieldName + '%')
              AND (@FieldValue IS NULL OR pci.Comments LIKE '%' + @FieldValue + '%')
              AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
              AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
              AND (@CategoryName IS NULL OR c.CategoryName LIKE '%' + @CategoryName + '%')
              AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
              AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
              AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
              AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
              AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
              AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
              AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities))
        )
        SELECT
            SiteName, TicketId, FieldName, FieldValue, CategoryName,
            PMcode, OperatorName, ChecklistDate, TicketStatus
        FROM RankedExtensions
        WHERE @LatestOnly = 0 OR RowNum = 1
        ORDER BY SiteName, CategoryName, FieldName;

        -- Extension summary
        ;WITH LatestExt AS (
            SELECT
                tk.SiteName, ce.Name AS FieldName, pci.Comments AS FieldValue, c.CategoryName,
                ROW_NUMBER() OVER (
                    PARTITION BY tk.SiteName, ce.Name
                    ORDER BY pc.ChecklistDate DESC, pc.Id DESC
                ) AS RowNum
            FROM dbo.Tickets tk
            INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
            INNER JOIN dbo.PMChecklistItems pci ON pci.PMChecklistId = pc.Id
            INNER JOIN dbo.CategoryExtension ce ON ce.Id = pci.CategoryExtensionId
            INNER JOIN dbo.Category c ON c.Id = pci.CategoryId
            LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
            WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
              AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
              AND pci.Comments IS NOT NULL AND LEN(LTRIM(RTRIM(pci.Comments))) > 0
              AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
              AND (@FieldName IS NULL OR ce.Name LIKE '%' + @FieldName + '%')
              AND (@FieldValue IS NULL OR pci.Comments LIKE '%' + @FieldValue + '%')
              AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
              AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
              AND (@CategoryName IS NULL OR c.CategoryName LIKE '%' + @CategoryName + '%')
              AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
              AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
              AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
              AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
              AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
              AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
              AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities))
        )
        SELECT
            COUNT(DISTINCT SiteName) AS TotalSites,
            COALESCE(@FieldName, 'All Fields') AS FieldFilter,
            COALESCE(@FieldValue, 'All Values') AS ValueFilter,
            COALESCE(@SiteName, 'All Sites') AS SiteFilter,
            COALESCE(@TicketStatus, 'All Statuses') AS StatusFilter,
            COALESCE(@TeamNames, 'All Teams') AS TeamFilter,
            COALESCE(@RegionNames, 'All Regions') AS RegionFilter,
            COALESCE(@CityNames, 'All Cities') AS CityFilter,
            COALESCE(CONVERT(NVARCHAR, @DateFrom, 23), 'No Start') AS DateFromFilter,
            COALESCE(CONVERT(NVARCHAR, @DateTo, 23), 'No End') AS DateToFilter,
            'Success' AS Message
        FROM LatestExt
        WHERE RowNum = 1;

        RETURN;
    END

    -- =========================================
    -- MODE 2: EQUIPMENT DATA (quantities - Door Contact, cameras, detectors, etc.)
    -- Triggered when @SubCategoryName is provided
    -- =========================================
    IF @SubCategoryName IS NOT NULL
    BEGIN
        ;WITH RankedEquipment AS (
            SELECT
                tk.SiteName,
                tk.Id AS TicketId,
                sc.SubCategoryName,
                pci.Quantity,
                pci.Physical,
                pci.Functionality,
                pci.Cleaning,
                pci.Repairing,
                c.CategoryName,
                pc.PMcode,
                pc.OperatorName,
                pc.ChecklistDate,
                lc.Name AS TicketStatus,
                ROW_NUMBER() OVER (
                    PARTITION BY tk.SiteName, sc.SubCategoryName
                    ORDER BY pc.ChecklistDate DESC, pc.Id DESC
                ) AS RowNum
            FROM dbo.Tickets tk
            INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
            INNER JOIN dbo.PMChecklistItems pci ON pci.PMChecklistId = pc.Id
            INNER JOIN dbo.SubCategory sc ON sc.Id = pci.SubCategoryId
            INNER JOIN dbo.Category c ON c.Id = pci.CategoryId
            LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
            WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
              AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
              AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
              AND (sc.SubCategoryName LIKE '%' + @SubCategoryName + '%')
              AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
              AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
              AND (@CategoryName IS NULL OR c.CategoryName LIKE '%' + @CategoryName + '%')
              AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
              AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
              AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
              AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
              AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
              AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
              AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities))
        )
        SELECT
            SiteName, TicketId, SubCategoryName, Quantity,
            Physical, Functionality, Cleaning, Repairing,
            CategoryName, PMcode, OperatorName, ChecklistDate, TicketStatus
        FROM RankedEquipment
        WHERE @LatestOnly = 0 OR RowNum = 1
        ORDER BY SiteName, CategoryName, SubCategoryName;

        -- Equipment summary
        ;WITH LatestEquip AS (
            SELECT
                tk.SiteName, sc.SubCategoryName, pci.Quantity,
                ROW_NUMBER() OVER (
                    PARTITION BY tk.SiteName, sc.SubCategoryName
                    ORDER BY pc.ChecklistDate DESC, pc.Id DESC
                ) AS RowNum
            FROM dbo.Tickets tk
            INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
            INNER JOIN dbo.PMChecklistItems pci ON pci.PMChecklistId = pc.Id
            INNER JOIN dbo.SubCategory sc ON sc.Id = pci.SubCategoryId
            INNER JOIN dbo.Category c ON c.Id = pci.CategoryId
            LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
            WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
              AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
              AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
              AND (sc.SubCategoryName LIKE '%' + @SubCategoryName + '%')
              AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
              AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
              AND (@CategoryName IS NULL OR c.CategoryName LIKE '%' + @CategoryName + '%')
              AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
              AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
              AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
              AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
              AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
              AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
              AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities))
        )
        SELECT
            COUNT(DISTINCT SiteName) AS TotalSites,
            SUM(Quantity) AS TotalQuantity,
            @SubCategoryName AS EquipmentFilter,
            COALESCE(@SiteName, 'All Sites') AS SiteFilter,
            COALESCE(@TicketStatus, 'All Statuses') AS StatusFilter,
            COALESCE(@TeamNames, 'All Teams') AS TeamFilter,
            COALESCE(@RegionNames, 'All Regions') AS RegionFilter,
            COALESCE(@CityNames, 'All Cities') AS CityFilter,
            COALESCE(CONVERT(NVARCHAR, @DateFrom, 23), 'No Start') AS DateFromFilter,
            COALESCE(CONVERT(NVARCHAR, @DateTo, 23), 'No End') AS DateToFilter,
            'Success' AS Message
        FROM LatestEquip
        WHERE RowNum = 1;

        RETURN;
    END

    -- =========================================
    -- MODE 3: PM CHECKLIST OVERVIEW (no FieldName, no SubCategoryName)
    -- Returns PM visit summary per site with PM codes
    -- =========================================
    SELECT
        tk.SiteName,
        tk.Id AS TicketId,
        pc.Id AS PMChecklistId,
        pc.PMcode,
        pc.OperatorName,
        pc.OperatorCode,
        pc.ChecklistDate,
        pc.GeneralComments,
        lc.Name AS TicketStatus,
        tm.Name AS TeamName,
        sp.Name AS RegionName,
        ci.Name AS CityName
    FROM dbo.Tickets tk
    INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
    INNER JOIN dbo.Teams tm ON tm.Id = tk.TeamId
    LEFT JOIN dbo.StateProvince sp ON sp.Id = tk.StateProvinceId
    LEFT JOIN dbo.City ci ON ci.Id = tk.CityId
    LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
    WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
      AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
      AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
      AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
      AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
      AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
      AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
      AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
      AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
      AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
      AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities))
    ORDER BY tk.SiteName, pc.ChecklistDate DESC;

    -- Overview summary
    SELECT
        COUNT(DISTINCT tk.SiteName) AS TotalSites,
        COUNT(DISTINCT pc.Id) AS TotalPMVisits,
        COALESCE(@SiteName, 'All Sites') AS SiteFilter,
        COALESCE(@PMCode, 'All PM Codes') AS PMCodeFilter,
        COALESCE(@TicketStatus, 'All Statuses') AS StatusFilter,
        COALESCE(@TeamNames, 'All Teams') AS TeamFilter,
        COALESCE(@RegionNames, 'All Regions') AS RegionFilter,
        COALESCE(@CityNames, 'All Cities') AS CityFilter,
        COALESCE(CONVERT(NVARCHAR, @DateFrom, 23), 'No Start') AS DateFromFilter,
        COALESCE(CONVERT(NVARCHAR, @DateTo, 23), 'No End') AS DateToFilter,
        'Success' AS Message
    FROM dbo.Tickets tk
    INNER JOIN dbo.PMChecklists pc ON pc.TicketId = tk.Id
    INNER JOIN dbo.Teams tm ON tm.Id = tk.TeamId
    LEFT JOIN dbo.StateProvince sp ON sp.Id = tk.StateProvinceId
    LEFT JOIN dbo.City ci ON ci.Id = tk.CityId
    LEFT JOIN dbo.LookupChild lc ON lc.Id = tk.CallStatusId
    WHERE tk.IsActive = 1 AND ISNULL(tk.IsDeleted, 0) = 0
      AND pc.IsActive = 1 AND ISNULL(pc.IsDeleted, 0) = 0
      AND (@SiteName IS NULL OR tk.SiteName LIKE '%' + @SiteName + '%')
      AND (@PMCode IS NULL OR pc.PMcode = @PMCode)
      AND (@TicketStatus IS NULL OR lc.Name LIKE '%' + @TicketStatus + '%')
      AND (@DateFrom IS NULL OR CAST(pc.ChecklistDate AS DATE) >= @DateFrom)
      AND (@DateTo IS NULL OR CAST(pc.ChecklistDate AS DATE) <= @DateTo)
      AND (@CanViewAll = 1 OR tk.TeamId IN (SELECT TeamId FROM @UserTeams))
      AND (@ProjectNames IS NULL OR tk.ProjectId IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@TeamNames IS NULL OR tk.TeamId IN (SELECT TeamId FROM @SelectedTeams))
      AND (@RegionNames IS NULL OR tk.StateProvinceId IN (SELECT RegionId FROM @SelectedRegions))
      AND (@CityNames IS NULL OR tk.CityId IN (SELECT CityId FROM @SelectedCities));
END
GO
