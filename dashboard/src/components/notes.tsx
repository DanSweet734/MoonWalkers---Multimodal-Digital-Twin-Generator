// What a twin or a job's reading notes say: identity, facts, parts, joints, control and issues,
// each with the sources it cites.

import type {
  ControlBehavior,
  Fact,
  Issue,
  Joint,
  MachineIdentity,
  Part,
  ScaleCalibration,
  Source,
} from '../api/types.gen.ts'
import { extents, factValue, percent, speed, triple } from '../lib/format.ts'
import { Citations } from './common.tsx'

type Sources = Map<string, Source>

export function IdentityBlock({ identity, sources }: { identity: MachineIdentity; sources: Sources }) {
  return (
    <dl className="facts-list">
      <dt>Machine</dt>
      <dd>
        {identity.manufacturer ?? '?'} {identity.model ?? '?'}
        {identity.category ? ` (${identity.category})` : ''}
      </dd>
      <dt>Confidence</dt>
      <dd>{percent(identity.confidence)}</dd>
      <dt>Sources</dt>
      <dd>
        <Citations citations={identity.citations} sources={sources} />
      </dd>
    </dl>
  )
}

export function FactsTable({ facts, sources }: { facts: Fact[]; sources: Sources }) {
  if (facts.length === 0) return <p className="muted">No facts recorded.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Fact</th>
            <th scope="col">Value (SI)</th>
            <th scope="col">As written</th>
            <th scope="col">Confidence</th>
            <th scope="col">Sources</th>
          </tr>
        </thead>
        <tbody>
          {facts.map((fact) => (
            <tr key={fact.key}>
              <th scope="row">
                <code>{fact.key}</code>
              </th>
              <td>{factValue(fact)}</td>
              <td>{fact.original ?? '-'}</td>
              <td>{percent(fact.confidence)}</td>
              <td>
                <Citations citations={fact.citations} sources={sources} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PartsTable({ parts, sources }: { parts: Part[]; sources: Sources }) {
  if (parts.length === 0) return null
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Part</th>
            <th scope="col">Size</th>
            <th scope="col">Geometry</th>
            <th scope="col">Sources</th>
          </tr>
        </thead>
        <tbody>
          {parts.map((part) => (
            <tr key={part.part_id}>
              <th scope="row">{part.name}</th>
              <td>{extents(part.bbox_min_m, part.bbox_max_m)}</td>
              <td>
                {part.geometry_file ? <code>{part.geometry_file}</code> : part.geometry_format}
                {part.generator ? ` (${part.generator.name} ${part.generator.version ?? ''})` : ''}
              </td>
              <td>
                <Citations citations={part.citations} sources={sources} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function JointsList({ joints, sources }: { joints: Joint[]; sources: Sources }) {
  return (
    <>
      {joints.map((joint) => (
        <dl className="facts-list" key={joint.joint_id}>
          <dt>Joint</dt>
          <dd>
            <code>{joint.joint_id}</code>: {joint.joint_type}, {joint.parent_part} →{' '}
            {joint.child_part}
          </dd>
          <dt>Axis, origin</dt>
          <dd>
            {triple(joint.axis)} at {triple(joint.origin_m)} m
          </dd>
          <dt>Limits</dt>
          <dd>
            {joint.lower_limit == null && joint.upper_limit == null
              ? 'none (turns freely)'
              : `${joint.lower_limit ?? '-'} to ${joint.upper_limit ?? '-'}`}
          </dd>
          <dt>Top speed</dt>
          <dd>{joint.max_velocity == null ? '-' : speed(joint.max_velocity)}</dd>
          <dt>Confidence</dt>
          <dd>{percent(joint.confidence)}</dd>
          <dt>Sources</dt>
          <dd>
            <Citations citations={joint.citations} sources={sources} />
          </dd>
        </dl>
      ))}
    </>
  )
}

export function ScaleBlock({ scale, sources }: { scale: ScaleCalibration; sources: Sources }) {
  return (
    <dl className="facts-list">
      <dt>Method</dt>
      <dd>
        {scale.method}
        {scale.reference ? `, from ${scale.reference}` : ''}
      </dd>
      <dt>Scale</dt>
      <dd>
        {scale.scale_factor == null ? '-' : `${scale.scale_factor.toFixed(6)} m per model unit`}
        {scale.known_value_m != null && scale.measured_model_units != null
          ? ` (${scale.known_value_m} m = ${scale.measured_model_units.toFixed(4)} model units)`
          : ''}
      </dd>
      <dt>Sources</dt>
      <dd>
        <Citations citations={scale.citations} sources={sources} />
      </dd>
    </dl>
  )
}

export function ControlList({ control, sources }: { control: ControlBehavior[]; sources: Sources }) {
  if (control.length === 0) return <p className="muted">No control behaviour recorded.</p>
  return (
    <>
      {control.map((behavior) => (
        <dl className="facts-list" key={behavior.behavior_id}>
          <dt>Behaviour</dt>
          <dd>
            {behavior.name} (<code>{behavior.behavior_id}</code>, {behavior.kind})
          </dd>
          <dt>What it does</dt>
          <dd>{behavior.description}</dd>
          {behavior.drives_joints && behavior.drives_joints.length > 0 ? (
            <>
              <dt>Drives</dt>
              <dd>{behavior.drives_joints.join(', ')}</dd>
            </>
          ) : null}
          {behavior.spec && Object.keys(behavior.spec).length > 0 ? (
            <>
              <dt>Details</dt>
              <dd>
                <pre>{JSON.stringify(behavior.spec, null, 2)}</pre>
              </dd>
            </>
          ) : null}
          <dt>Sources</dt>
          <dd>
            <Citations citations={behavior.citations} sources={sources} />
          </dd>
        </dl>
      ))}
    </>
  )
}

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0) return <p className="muted">No issues recorded.</p>
  return (
    <ul className="issues">
      {issues.map((issue, i) => (
        <li key={i} className={`issue issue-${issue.severity}`}>
          <strong>{issue.severity}</strong>
          {issue.ref ? (
            <>
              {' '}
              (<code>{issue.ref}</code>)
            </>
          ) : null}
          : {issue.message}
        </li>
      ))}
    </ul>
  )
}
