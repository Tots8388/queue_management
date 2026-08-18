import { PatientStatusView } from "./PatientStatusView";

// `params` is typed inline rather than with the generated `PageProps` helper:
// that global only exists once a build has run, and `npm run typecheck`
// deliberately excludes generated types so a clean checkout can be checked
// without building first.
type PatientTokenPageProps = {
  params: Promise<{ token: string }>;
};

export async function generateMetadata(props: PatientTokenPageProps) {
  const { token } = await props.params;
  return { title: `Token ${decodeURIComponent(token)}` };
}

export default async function PatientTokenPage(props: PatientTokenPageProps) {
  const { token } = await props.params;
  return <PatientStatusView token={decodeURIComponent(token)} />;
}
