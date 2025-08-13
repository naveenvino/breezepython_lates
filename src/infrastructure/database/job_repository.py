"""
Database repository for background job tracking
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import pyodbc
from dataclasses import dataclass
import os
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(Enum):
    DATA_COLLECTION = "data_collection"
    ML_VALIDATION = "ml_validation"
    BACKTEST = "backtest"
    AUTO_LOGIN = "auto_login"
    SCHEDULER = "scheduler"

@dataclass
class BackgroundJob:
    id: str
    job_id: str
    job_type: str
    status: str
    message: Optional[str]
    progress_percent: int
    created_by: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    updated_at: datetime
    completed_at: Optional[datetime]
    result_data: Optional[Dict[str, Any]]
    error_details: Optional[str]

class JobRepository:
    def __init__(self):
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_SERVER', '(localdb)\\mssqllocaldb')};"
            f"DATABASE={os.getenv('DB_NAME', 'KiteConnectApi')};"
            f"Trusted_Connection=yes;"
        )
    
    def _get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def create_job(
        self,
        job_type: str,
        created_by: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """Create a new background job"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            job_id = str(uuid4())
            
            cursor.execute("""
                INSERT INTO BackgroundJobs (
                    job_id, job_type, status, message, 
                    progress_percent, created_by, 
                    created_at, updated_at
                ) 
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, 0, ?, GETDATE(), GETDATE())
            """, (
                job_id, job_type, JobStatus.PENDING.value, 
                message, created_by
            ))
            
            row_id = cursor.fetchone()[0]
            conn.commit()
            
            return job_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        message: Optional[str] = None,
        progress_percent: Optional[int] = None,
        result_data: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """Update job status and progress"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Build update query dynamically
            updates = ["status = ?", "updated_at = GETDATE()"]
            params = [status.value]
            
            if message is not None:
                updates.append("message = ?")
                params.append(message)
            
            if progress_percent is not None:
                updates.append("progress_percent = ?")
                params.append(progress_percent)
            
            if status == JobStatus.RUNNING:
                updates.append("started_at = COALESCE(started_at, GETDATE())")
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                updates.append("completed_at = GETDATE()")
            
            if result_data is not None:
                updates.append("result_data = ?")
                params.append(json.dumps(result_data))
            
            if error_details is not None:
                updates.append("error_details = ?")
                params.append(error_details)
            
            params.append(job_id)
            
            query = f"""
                UPDATE BackgroundJobs 
                SET {', '.join(updates)}
                WHERE job_id = ?
            """
            
            cursor.execute(query, params)
            conn.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get job by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, job_id, job_type, status, message,
                    progress_percent, created_by, created_at,
                    started_at, updated_at, completed_at,
                    result_data, error_details
                FROM BackgroundJobs
                WHERE job_id = ?
            """, job_id)
            
            row = cursor.fetchone()
            if row:
                return BackgroundJob(
                    id=str(row[0]),
                    job_id=row[1],
                    job_type=row[2],
                    status=row[3],
                    message=row[4],
                    progress_percent=row[5] or 0,
                    created_by=row[6],
                    created_at=row[7],
                    started_at=row[8],
                    updated_at=row[9],
                    completed_at=row[10],
                    result_data=json.loads(row[11]) if row[11] else None,
                    error_details=row[12]
                )
            return None
            
        finally:
            cursor.close()
            conn.close()
    
    def get_jobs_by_status(
        self, 
        status: JobStatus,
        job_type: Optional[str] = None,
        limit: int = 100
    ) -> List[BackgroundJob]:
        """Get jobs by status and optionally type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if job_type:
                cursor.execute("""
                    SELECT TOP(?)
                        id, job_id, job_type, status, message,
                        progress_percent, created_by, created_at,
                        started_at, updated_at, completed_at,
                        result_data, error_details
                    FROM BackgroundJobs
                    WHERE status = ? AND job_type = ?
                    ORDER BY created_at DESC
                """, (limit, status.value, job_type))
            else:
                cursor.execute("""
                    SELECT TOP(?)
                        id, job_id, job_type, status, message,
                        progress_percent, created_by, created_at,
                        started_at, updated_at, completed_at,
                        result_data, error_details
                    FROM BackgroundJobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (limit, status.value))
            
            jobs = []
            for row in cursor.fetchall():
                jobs.append(BackgroundJob(
                    id=str(row[0]),
                    job_id=row[1],
                    job_type=row[2],
                    status=row[3],
                    message=row[4],
                    progress_percent=row[5] or 0,
                    created_by=row[6],
                    created_at=row[7],
                    started_at=row[8],
                    updated_at=row[9],
                    completed_at=row[10],
                    result_data=json.loads(row[11]) if row[11] else None,
                    error_details=row[12]
                ))
            
            return jobs
            
        finally:
            cursor.close()
            conn.close()
    
    def get_recent_jobs(
        self,
        limit: int = 10,
        job_type: Optional[str] = None
    ) -> List[BackgroundJob]:
        """Get recent jobs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if job_type:
                cursor.execute("""
                    SELECT TOP(?)
                        id, job_id, job_type, status, message,
                        progress_percent, created_by, created_at,
                        started_at, updated_at, completed_at,
                        result_data, error_details
                    FROM BackgroundJobs
                    WHERE job_type = ?
                    ORDER BY created_at DESC
                """, (limit, job_type))
            else:
                cursor.execute("""
                    SELECT TOP(?)
                        id, job_id, job_type, status, message,
                        progress_percent, created_by, created_at,
                        started_at, updated_at, completed_at,
                        result_data, error_details
                    FROM BackgroundJobs
                    ORDER BY created_at DESC
                """, limit)
            
            jobs = []
            for row in cursor.fetchall():
                jobs.append(BackgroundJob(
                    id=str(row[0]),
                    job_id=row[1],
                    job_type=row[2],
                    status=row[3],
                    message=row[4],
                    progress_percent=row[5] or 0,
                    created_by=row[6],
                    created_at=row[7],
                    started_at=row[8],
                    updated_at=row[9],
                    completed_at=row[10],
                    result_data=json.loads(row[11]) if row[11] else None,
                    error_details=row[12]
                ))
            
            return jobs
            
        finally:
            cursor.close()
            conn.close()
    
    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up jobs older than specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM BackgroundJobs
                WHERE created_at < DATEADD(day, -?, GETDATE())
                    AND status IN (?, ?)
            """, (days, JobStatus.COMPLETED.value, JobStatus.FAILED.value))
            
            count = cursor.rowcount
            conn.commit()
            return count
            
        finally:
            cursor.close()
            conn.close()

# Singleton instance
_job_repository = None

def get_job_repository() -> JobRepository:
    global _job_repository
    if _job_repository is None:
        _job_repository = JobRepository()
    return _job_repository