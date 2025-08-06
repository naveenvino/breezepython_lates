-- Create TradingHolidays table
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

-- Create index for faster lookups
CREATE INDEX IX_TradingHolidays_Exchange_Date 
ON TradingHolidays(Exchange, HolidayDate);

-- Create unique constraint to prevent duplicate entries
CREATE UNIQUE INDEX IX_TradingHolidays_Unique 
ON TradingHolidays(Exchange, HolidayDate);

-- Insert NSE holidays for 2025
INSERT INTO TradingHolidays (Exchange, HolidayDate, HolidayName, HolidayType, IsTradingHoliday, IsSettlementHoliday)
VALUES 
    ('NSE', '2025-01-26', 'Republic Day', 'Trading Holiday', 1, 0),
    ('NSE', '2025-03-14', 'Holi', 'Trading Holiday', 1, 0),
    ('NSE', '2025-03-31', 'Ram Navami', 'Trading Holiday', 1, 0),
    ('NSE', '2025-04-10', 'Mahavir Jayanti', 'Trading Holiday', 1, 0),
    ('NSE', '2025-04-14', 'Ambedkar Jayanti', 'Trading Holiday', 1, 0),
    ('NSE', '2025-04-18', 'Good Friday', 'Trading Holiday', 1, 0),
    ('NSE', '2025-05-01', 'Maharashtra Day', 'Trading Holiday', 1, 0),
    ('NSE', '2025-08-15', 'Independence Day', 'Trading Holiday', 1, 0),
    ('NSE', '2025-08-27', 'Ganesh Chaturthi', 'Trading Holiday', 1, 0),
    ('NSE', '2025-10-02', 'Gandhi Jayanti', 'Trading Holiday', 1, 0),
    ('NSE', '2025-10-21', 'Dussehra', 'Trading Holiday', 1, 0),
    ('NSE', '2025-11-10', 'Diwali - Laxmi Pujan', 'Trading Holiday', 1, 0),
    ('NSE', '2025-11-11', 'Diwali - Balipratipada', 'Trading Holiday', 1, 0),
    ('NSE', '2025-11-14', 'Guru Nanak Jayanti', 'Trading Holiday', 1, 0),
    ('NSE', '2025-12-25', 'Christmas', 'Trading Holiday', 1, 0);

-- Sample query to check holidays
SELECT * FROM TradingHolidays 
WHERE Exchange = 'NSE' 
AND YEAR(HolidayDate) = 2025
ORDER BY HolidayDate;