import { PatientStatusView } from "./PatientStatusView";

export async function generateMetadata(props: PageProps<"/patient/[token]">) {
  const { token } = await props.params;
  return { title: `Token ${decodeURIComponent(token)}` };
}

export default async function PatientTokenPage(
  props: PageProps<"/patient/[token]">,
) {
  const { token } = await props.params;
  return <PatientStatusView token={decodeURIComponent(token)} />;
}
