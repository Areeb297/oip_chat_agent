USE [TickTraq]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE OR ALTER PROCEDURE [dbo].[usp_Chatbot_GetInventoryConsumption]
(
    @Username NVARCHAR(100),
    @ProjectNames NVARCHAR(MAX) = NULL,        -- Comma-separated project names
    @ItemName NVARCHAR(200) = NULL,            -- Partial match on Inventory.Name
    @ItemCode NVARCHAR(200) = NULL,            -- Partial match on Inventory.Code
    @CategoryName NVARCHAR(200) = NULL,        -- Partial match on Category name (via SubCategory)
    @Month INT = NULL,                         -- 1-12
    @Year INT = NULL,                          -- 2020-2030
    @DateFrom DATE = NULL,                     -- Start date filter on InventoryTransaction.CreatedAt
    @DateTo DATE = NULL,                       -- End date filter on InventoryTransaction.CreatedAt
    @TransactionType NVARCHAR(10) = 'OUT'      -- 'OUT' (consumed), 'IN' (returned), 'ALL'
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
        SELECT 0 AS TotalTransactions, 'User not found' AS Message;
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
            SELECT 0 AS TotalTransactions, 'No matching projects found' AS Message;
            RETURN;
        END
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
    -- RESULT SET 1: TRANSACTION DETAIL
    -- Join chain: InventoryTransaction -> Inventory -> InventoryRequest (via ReferenceId) -> Location/Ticket for site
    -- =========================================
    SELECT
        inv.Name AS ItemName,
        inv.Code AS ItemCode,
        inv.Model AS ItemModel,
        sc.SubCategoryName AS CategoryName,
        it.TransactionType,
        it.Quantity,
        CAST(it.CreatedAt AS DATE) AS TransactionDate,
        p.Name AS ProjectName,
        -- Site resolution: try Location first, then Ticket.SiteName
        COALESCE(loc.LocationName, tk.SiteName, 'N/A') AS SiteName,
        ir.RequestNo,
        v.Name AS VendorName
    FROM dbo.InventoryTransaction it
    INNER JOIN dbo.Inventory inv ON inv.Id = it.InventoryId
    LEFT JOIN dbo.SubCategory sc ON sc.Id = inv.SubCategoryId
    -- Link to InventoryRequest via ReferenceId when ReferenceType = 'InventoryRequest'
    LEFT JOIN dbo.InventoryRequest ir ON ir.Id = it.ReferenceId AND it.ReferenceType = 'InventoryRequest'
    LEFT JOIN dbo.Location loc ON loc.Id = ir.LocationId
    LEFT JOIN dbo.Tickets tk ON tk.Id = ir.TicketId
    LEFT JOIN dbo.Projects p ON p.Id = COALESCE(ir.ProjectId, inv.ProjectId)
    LEFT JOIN dbo.Vendors v ON v.Id = inv.VendorId
    WHERE it.IsActive = 1 AND ISNULL(it.IsDeleted, 0) = 0
      AND inv.IsActive = 1 AND ISNULL(inv.IsDeleted, 0) = 0
      -- Transaction type filter
      AND (@TransactionType = 'ALL' OR it.TransactionType = @TransactionType)
      -- Item filters
      AND (@ItemName IS NULL OR inv.Name LIKE '%' + @ItemName + '%')
      AND (@ItemCode IS NULL OR inv.Code LIKE '%' + @ItemCode + '%')
      AND (@CategoryName IS NULL OR sc.SubCategoryName LIKE '%' + @CategoryName + '%')
      -- Project filter (on request project or inventory project)
      AND (@ProjectNames IS NULL OR COALESCE(ir.ProjectId, inv.ProjectId) IN (SELECT ProjectId FROM @SelectedProjects))
      -- Date filters on transaction date
      AND (@FilterDateFrom IS NULL OR CAST(it.CreatedAt AS DATE) >= @FilterDateFrom)
      AND (@FilterDateTo IS NULL OR CAST(it.CreatedAt AS DATE) <= @FilterDateTo)
      -- Access control: user must have access to the project
      AND (@CanViewAll = 1
           OR COALESCE(ir.ProjectId, inv.ProjectId) IN (SELECT ProjectId FROM @UserTeams)
           OR COALESCE(ir.ProjectId, inv.ProjectId) IS NULL)
    ORDER BY it.CreatedAt DESC, inv.Name;

    -- =========================================
    -- RESULT SET 2: SUMMARY
    -- =========================================
    SELECT
        COUNT(it.Id) AS TotalTransactions,
        COUNT(DISTINCT inv.Id) AS UniqueItems,
        ISNULL(SUM(it.Quantity), 0) AS TotalQuantity,
        COUNT(DISTINCT COALESCE(loc.LocationName, tk.SiteName)) AS UniqueSites,
        COALESCE(@ItemName, 'All Items') AS ItemNameFilter,
        COALESCE(@ItemCode, 'All Codes') AS ItemCodeFilter,
        COALESCE(@CategoryName, 'All Categories') AS CategoryFilter,
        COALESCE(@ProjectNames, 'All Projects') AS ProjectFilter,
        COALESCE(@TransactionType, 'OUT') AS TransactionTypeFilter,
        COALESCE(CONVERT(NVARCHAR, @FilterDateFrom, 23), 'No Start') AS DateFromFilter,
        COALESCE(CONVERT(NVARCHAR, @FilterDateTo, 23), 'No End') AS DateToFilter,
        'Success' AS Message
    FROM dbo.InventoryTransaction it
    INNER JOIN dbo.Inventory inv ON inv.Id = it.InventoryId
    LEFT JOIN dbo.SubCategory sc ON sc.Id = inv.SubCategoryId
    LEFT JOIN dbo.InventoryRequest ir ON ir.Id = it.ReferenceId AND it.ReferenceType = 'InventoryRequest'
    LEFT JOIN dbo.Location loc ON loc.Id = ir.LocationId
    LEFT JOIN dbo.Tickets tk ON tk.Id = ir.TicketId
    WHERE it.IsActive = 1 AND ISNULL(it.IsDeleted, 0) = 0
      AND inv.IsActive = 1 AND ISNULL(inv.IsDeleted, 0) = 0
      AND (@TransactionType = 'ALL' OR it.TransactionType = @TransactionType)
      AND (@ItemName IS NULL OR inv.Name LIKE '%' + @ItemName + '%')
      AND (@ItemCode IS NULL OR inv.Code LIKE '%' + @ItemCode + '%')
      AND (@CategoryName IS NULL OR sc.SubCategoryName LIKE '%' + @CategoryName + '%')
      AND (@ProjectNames IS NULL OR COALESCE(ir.ProjectId, inv.ProjectId) IN (SELECT ProjectId FROM @SelectedProjects))
      AND (@FilterDateFrom IS NULL OR CAST(it.CreatedAt AS DATE) >= @FilterDateFrom)
      AND (@FilterDateTo IS NULL OR CAST(it.CreatedAt AS DATE) <= @FilterDateTo)
      AND (@CanViewAll = 1
           OR COALESCE(ir.ProjectId, inv.ProjectId) IN (SELECT ProjectId FROM @UserTeams)
           OR COALESCE(ir.ProjectId, inv.ProjectId) IS NULL);
END
GO
