-- Load NSE holidays for multiple years (2022-2025)
-- Run this script if you want to load holidays directly in SQL

-- First, ensure the table exists
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='TradingHolidays' AND xtype='U')
BEGIN
    CREATE TABLE TradingHolidays (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Exchange NVARCHAR(10) NOT NULL,
        HolidayDate DATE NOT NULL,
        HolidayName NVARCHAR(100) NOT NULL,
        HolidayType NVARCHAR(50) NULL,
        IsTradingHoliday BIT NOT NULL DEFAULT 1,
        IsSettlementHoliday BIT NOT NULL DEFAULT 0,
        CreatedAt DATETIME NOT NULL DEFAULT GETUTCDATE(),
        UpdatedAt DATETIME NOT NULL DEFAULT GETUTCDATE()
    );
    
    CREATE INDEX IX_TradingHolidays_Exchange_Date 
    ON TradingHolidays(Exchange, HolidayDate);
    
    CREATE UNIQUE INDEX IX_TradingHolidays_Unique 
    ON TradingHolidays(Exchange, HolidayDate);
END

-- Clear existing data (optional - comment out if you want to keep existing data)
-- DELETE FROM TradingHolidays WHERE Exchange = 'NSE';

-- Insert NSE holidays for 2022
INSERT INTO TradingHolidays (Exchange, HolidayDate, HolidayName, HolidayType, IsTradingHoliday, IsSettlementHoliday)
SELECT 'NSE', HolidayDate, HolidayName, 'Trading Holiday', 1, 0
FROM (VALUES
    ('2022-01-26', 'Republic Day'),
    ('2022-03-01', 'Mahashivratri'),
    ('2022-03-18', 'Holi'),
    ('2022-04-14', 'Ambedkar Jayanti'),
    ('2022-04-15', 'Good Friday'),
    ('2022-05-03', 'Id-Ul-Fitr'),
    ('2022-08-09', 'Muharram'),
    ('2022-08-15', 'Independence Day'),
    ('2022-08-31', 'Ganesh Chaturthi'),
    ('2022-10-05', 'Dussehra'),
    ('2022-10-24', 'Diwali - Laxmi Pujan'),
    ('2022-10-26', 'Diwali - Balipratipada'),
    ('2022-11-08', 'Guru Nanak Jayanti')
) AS Holidays(HolidayDate, HolidayName)
WHERE NOT EXISTS (
    SELECT 1 FROM TradingHolidays 
    WHERE Exchange = 'NSE' AND HolidayDate = Holidays.HolidayDate
);

-- Insert NSE holidays for 2023
INSERT INTO TradingHolidays (Exchange, HolidayDate, HolidayName, HolidayType, IsTradingHoliday, IsSettlementHoliday)
SELECT 'NSE', HolidayDate, HolidayName, 'Trading Holiday', 1, 0
FROM (VALUES
    ('2023-01-26', 'Republic Day'),
    ('2023-03-07', 'Holi'),
    ('2023-03-30', 'Ram Navami'),
    ('2023-04-04', 'Mahavir Jayanti'),
    ('2023-04-07', 'Good Friday'),
    ('2023-04-14', 'Ambedkar Jayanti'),
    ('2023-05-01', 'Maharashtra Day'),
    ('2023-06-29', 'Bakri Id'),
    ('2023-08-15', 'Independence Day'),
    ('2023-09-19', 'Ganesh Chaturthi'),
    ('2023-10-02', 'Gandhi Jayanti'),
    ('2023-10-24', 'Dussehra'),
    ('2023-11-13', 'Diwali - Laxmi Pujan'),
    ('2023-11-14', 'Diwali - Balipratipada'),
    ('2023-11-27', 'Guru Nanak Jayanti'),
    ('2023-12-25', 'Christmas')
) AS Holidays(HolidayDate, HolidayName)
WHERE NOT EXISTS (
    SELECT 1 FROM TradingHolidays 
    WHERE Exchange = 'NSE' AND HolidayDate = Holidays.HolidayDate
);

-- Insert NSE holidays for 2024
INSERT INTO TradingHolidays (Exchange, HolidayDate, HolidayName, HolidayType, IsTradingHoliday, IsSettlementHoliday)
SELECT 'NSE', HolidayDate, HolidayName, 'Trading Holiday', 1, 0
FROM (VALUES
    ('2024-01-26', 'Republic Day'),
    ('2024-03-08', 'Mahashivratri'),
    ('2024-03-25', 'Holi'),
    ('2024-03-29', 'Good Friday'),
    ('2024-04-11', 'Id-Ul-Fitr'),
    ('2024-04-17', 'Ram Navami'),
    ('2024-05-01', 'Maharashtra Day'),
    ('2024-06-17', 'Bakri Id'),
    ('2024-07-17', 'Muharram'),
    ('2024-08-15', 'Independence Day'),
    ('2024-10-02', 'Gandhi Jayanti'),
    ('2024-11-01', 'Diwali - Laxmi Pujan'),
    ('2024-11-15', 'Guru Nanak Jayanti'),
    ('2024-12-25', 'Christmas')
) AS Holidays(HolidayDate, HolidayName)
WHERE NOT EXISTS (
    SELECT 1 FROM TradingHolidays 
    WHERE Exchange = 'NSE' AND HolidayDate = Holidays.HolidayDate
);

-- Insert NSE holidays for 2025
INSERT INTO TradingHolidays (Exchange, HolidayDate, HolidayName, HolidayType, IsTradingHoliday, IsSettlementHoliday)
SELECT 'NSE', HolidayDate, HolidayName, 'Trading Holiday', 1, 0
FROM (VALUES
    ('2025-01-26', 'Republic Day'),
    ('2025-03-14', 'Holi'),
    ('2025-03-31', 'Ram Navami'),
    ('2025-04-10', 'Mahavir Jayanti'),
    ('2025-04-14', 'Ambedkar Jayanti'),
    ('2025-04-18', 'Good Friday'),
    ('2025-05-01', 'Maharashtra Day'),
    ('2025-08-15', 'Independence Day'),
    ('2025-08-27', 'Ganesh Chaturthi'),
    ('2025-10-02', 'Gandhi Jayanti'),
    ('2025-10-21', 'Dussehra'),
    ('2025-11-10', 'Diwali - Laxmi Pujan'),
    ('2025-11-11', 'Diwali - Balipratipada'),
    ('2025-11-14', 'Guru Nanak Jayanti'),
    ('2025-12-25', 'Christmas')
) AS Holidays(HolidayDate, HolidayName)
WHERE NOT EXISTS (
    SELECT 1 FROM TradingHolidays 
    WHERE Exchange = 'NSE' AND HolidayDate = Holidays.HolidayDate
);

-- Summary query
SELECT 
    YEAR(HolidayDate) as Year,
    COUNT(*) as TotalHolidays
FROM TradingHolidays
WHERE Exchange = 'NSE'
GROUP BY YEAR(HolidayDate)
ORDER BY Year;

-- Show all holidays
SELECT 
    YEAR(HolidayDate) as Year,
    HolidayDate,
    HolidayName,
    DATENAME(WEEKDAY, HolidayDate) as DayOfWeek
FROM TradingHolidays
WHERE Exchange = 'NSE'
ORDER BY HolidayDate;