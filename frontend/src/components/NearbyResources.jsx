import { useState } from 'react';

import { searchNearbyResources } from '../services/api';
import { getToken } from '../services/auth';

const CATEGORIES = [
  { value: 'study_space', label: 'Study spaces' },
  { value: 'library', label: 'Libraries' },
  { value: 'college', label: 'Colleges and universities' },
];

function NearbyResources() {
  const [category, setCategory] = useState('study_space');
  const [radiusM, setRadiusM] = useState(2000);
  const [location, setLocation] = useState('');
  const [locationLabel, setLocationLabel] = useState('');
  const [results, setResults] = useState([]);
  const [attributionUrl, setAttributionUrl] = useState('https://www.openstreetmap.org/copyright');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function runSearch(search) {
    setLoading(true);
    setError('');
    setResults([]);
    try {
      const data = await searchNearbyResources(getToken(), search, Number(radiusM), category);
      setResults(data.results || []);
      setAttributionUrl(data.attribution_url || 'https://www.openstreetmap.org/copyright');
      setLocationLabel(data.location_label || '');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function findCity(event) {
    event.preventDefault();
    if (location.trim().length < 2) {
      setError('Enter a city or town name.');
      return;
    }
    runSearch({ location: location.trim() });
  }

  function findNearby() {
    if (!navigator.geolocation) {
      setError('This browser does not provide location access.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        runSearch({ latitude: coords.latitude, longitude: coords.longitude });
      },
      (locationError) => {
        setError(locationError.code === locationError.PERMISSION_DENIED
          ? 'Location permission was declined. You can search by city below.'
          : 'Your location could not be determined. Try again or search by city below.');
      },
      { enableHighAccuracy: false, maximumAge: 60_000, timeout: 12_000 },
    );
  }

  return (
    <section className="border-top mt-4 pt-3">
      <h2 className="h6 fw-bold mb-1">Nearby learning places</h2>
      <p className="small text-muted">
        Search by city or choose location access. Your city or approximate coordinates are sent to configured map services for this search, not saved in chat. Avoid private or precise home addresses.
      </p>
      <div className="d-grid gap-2 mb-3">
        <label className="visually-hidden" htmlFor="nearby-category">Place type</label>
        <select id="nearby-category" className="form-select form-select-sm" value={category} onChange={(event) => setCategory(event.target.value)}>
          {CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <label className="visually-hidden" htmlFor="nearby-radius">Search radius</label>
        <select id="nearby-radius" className="form-select form-select-sm" value={radiusM} onChange={(event) => setRadiusM(event.target.value)}>
          <option value={1000}>Within 1 km</option>
          <option value={2000}>Within 2 km</option>
          <option value={5000}>Within 5 km</option>
        </select>
        <form className="d-flex gap-2" onSubmit={findCity}>
          <label className="visually-hidden" htmlFor="nearby-city">City or town</label>
          <input id="nearby-city" className="form-control form-control-sm" value={location} onChange={(event) => setLocation(event.target.value)} maxLength={160} placeholder="City or town" />
          <button type="submit" className="btn btn-outline-dark btn-sm flex-shrink-0" disabled={loading || location.trim().length < 2}>
            Search
          </button>
        </form>
        <button type="button" className="btn btn-outline-dark btn-sm" disabled={loading} onClick={findNearby}>
          {loading ? 'Searching nearby…' : 'Use my location'}
        </button>
      </div>
      {error && <div className="alert alert-warning small py-2">{error}</div>}
      {locationLabel && <p className="small fw-semibold">Places near {locationLabel}</p>}
      {!loading && results.length === 0 && !error && <p className="small text-muted">No nearby places found yet.</p>}
      {results.length > 0 && (
        <div className="d-grid gap-2">
          {results.map((item, index) => (
            <a key={`${item.title}-${item.latitude}-${item.longitude}-${index}`} href={/^https:\/\//i.test(item.url || '') ? item.url : undefined} target="_blank" rel="noreferrer" className="text-decoration-none border rounded-2 p-2">
              <span className="small fw-semibold d-block">{item.title}</span>
              <span className="small text-muted">{item.snippet}</span>
            </a>
          ))}
        </div>
      )}
      <p className="small text-muted mt-2 mb-0">
        Distances are approximate · <a href={attributionUrl} target="_blank" rel="noreferrer">© OpenStreetMap contributors</a> · <a href="https://operations.osmfoundation.org/policies/nominatim/" target="_blank" rel="noreferrer">geocoder usage policy</a>
      </p>
    </section>
  );
}

export default NearbyResources;

// FILE PURPOSE:
// Lets users opt in to nearby educational-place searches and displays
// distance-ranked OpenStreetMap results with attribution.
