import uuid
from app.core.database import SessionLocal, Job, Experiment


class JobManager:

    def create_job(self, user_id):
        session = SessionLocal()

        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            user_id=user_id,
            status="processing",
            output_path=""
        )

        session.add(job)
        session.commit()
        session.close()

        return job_id

    def update_job(self, job_id, status, output_path=None):
        session = SessionLocal()

        job = session.query(Job).filter(Job.id == job_id).first()

        if job:
            job.status = status
            if output_path:
                job.output_path = output_path
            session.commit()

        session.close()

    def get_job(self, job_id, user_id):
        session = SessionLocal()

        job = session.query(Job).filter(
            Job.id == job_id,
            Job.user_id == user_id
        ).first()

        if not job:
            session.close()
            return None

        data = {
            "status": job.status,
            "output_path": job.output_path
        }

        session.close()
        return data

    def save_experiment(self, job_id, final_score, sampling_rate, offset_ms, unit_corrected):
        session = SessionLocal()

        exp = Experiment(
            id=str(uuid.uuid4()),
            job_id=job_id,
            final_score=final_score,
            sampling_rate=sampling_rate,
            offset_ms=offset_ms,
            unit_corrected=str(unit_corrected),
        )

        session.add(exp)
        session.commit()
        session.close()
