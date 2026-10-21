-- Historical case references must outlive an explicitly authorized case deletion.
-- Existing audit rows and their case IDs remain byte-for-byte unchanged.
BEGIN;
CREATE TABLE audit_case_references (
 id uuid PRIMARY KEY,
 business_number varchar(120) NOT NULL,
 operator_initials varchar(12) NOT NULL,
 retained_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO audit_case_references(id,business_number,operator_initials)
 SELECT id,business_number,operator_initials FROM cases;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_case_id_fkey;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_case_id_fkey
 FOREIGN KEY(case_id) REFERENCES audit_case_references(id);
CREATE FUNCTION retain_audit_case_reference() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
 BEGIN
  INSERT INTO public.audit_case_references(id,business_number,operator_initials)
   VALUES(NEW.id,NEW.business_number,NEW.operator_initials);
  RETURN NEW;
 END;
 $$;
REVOKE ALL ON FUNCTION retain_audit_case_reference() FROM PUBLIC;
CREATE TRIGGER retain_audit_case_reference AFTER INSERT ON cases
 FOR EACH ROW EXECUTE FUNCTION retain_audit_case_reference();
INSERT INTO schema_migrations(version,name) VALUES(7,'audit_case_retention');
COMMIT;
